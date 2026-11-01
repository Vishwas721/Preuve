from types import SimpleNamespace

import pytest
from google.genai import errors
from pydantic import BaseModel

from app.llm.base import LLMOutputError, LLMRateLimitError, LLMUnavailableError
from app.llm.gemini import GeminiProvider

MODELS = ["m-best", "m-mid", "m-old"]


class Label(BaseModel):
    label: str


def api_error(code: int) -> errors.APIError:
    return errors.APIError(code, {"error": {"code": code, "message": "x", "status": "X"}})


class FakeModels:
    """Stands in for `client.aio.models`: per-model scripted results, records call order."""

    def __init__(self, script: dict[str, list]) -> None:
        self.script = script
        self.calls: list[str] = []

    async def generate_content(self, *, model: str, contents: str, config: object):
        self.calls.append(model)
        outcome = self.script[model].pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(text=outcome)


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def make(script: dict[str, list], clock: Clock | None = None):
    models = FakeModels(script)
    client = SimpleNamespace(aio=SimpleNamespace(models=models))
    provider = GeminiProvider("", MODELS, client=client, cooldown_s=60, clock=clock or Clock())
    return provider, models


async def test_uses_first_model_when_healthy() -> None:
    provider, models = make({"m-best": ['{"label": "a"}']})
    assert (await provider.generate_structured("p", Label)).label == "a"
    assert models.calls == ["m-best"]


async def test_falls_back_on_server_error_and_rate_limit() -> None:
    provider, models = make(
        {"m-best": [api_error(504)], "m-mid": [api_error(429)], "m-old": ['{"label": "c"}']}
    )
    assert (await provider.generate_structured("p", Label)).label == "c"
    assert models.calls == ["m-best", "m-mid", "m-old"]


async def test_falls_back_on_timeout() -> None:
    provider, models = make({"m-best": [TimeoutError()], "m-mid": ["hello"]})
    assert await provider.generate_text("p") == "hello"
    assert models.calls == ["m-best", "m-mid"]


async def test_falls_back_on_invalid_output() -> None:
    provider, models = make({"m-best": ["not json"], "m-mid": ['{"label": "b"}']})
    assert (await provider.generate_structured("p", Label)).label == "b"


async def test_failed_model_is_skipped_during_cooldown_then_retried() -> None:
    clock = Clock()
    provider, models = make(
        {
            "m-best": [api_error(503), '{"label": "back"}'],
            "m-mid": ['{"label": "1"}', '{"label": "2"}'],
        },
        clock,
    )
    await provider.generate_structured("p", Label)
    await provider.generate_structured("p", Label)  # m-best still cooling down
    assert models.calls == ["m-best", "m-mid", "m-mid"]

    clock.now = 61  # cooldown over
    assert (await provider.generate_structured("p", Label)).label == "back"
    assert models.calls[-1] == "m-best"


async def test_invalid_output_does_not_cool_down() -> None:
    provider, models = make({"m-best": ["bad", '{"label": "a"}'], "m-mid": ['{"label": "b"}']})
    await provider.generate_structured("p", Label)
    assert (await provider.generate_structured("p", Label)).label == "a"
    assert models.calls == ["m-best", "m-mid", "m-best"]


async def test_all_rate_limited_raises_rate_limit() -> None:
    provider, _ = make({m: [api_error(429)] for m in MODELS})
    with pytest.raises(LLMRateLimitError):
        await provider.generate_text("p")


async def test_all_down_raises_unavailable() -> None:
    provider, _ = make(
        {"m-best": [api_error(500)], "m-mid": [api_error(429)], "m-old": [api_error(404)]}
    )
    with pytest.raises(LLMUnavailableError) as exc_info:
        await provider.generate_text("p")
    assert not isinstance(exc_info.value, LLMRateLimitError)


async def test_all_invalid_output_raises_output_error() -> None:
    provider, _ = make({m: ["nope"] for m in MODELS})
    with pytest.raises(LLMOutputError):
        await provider.generate_structured("p", Label)


async def test_not_configured() -> None:
    provider = GeminiProvider("", MODELS)
    assert not await provider.is_available()
    with pytest.raises(LLMUnavailableError):
        await provider.generate_text("p")
