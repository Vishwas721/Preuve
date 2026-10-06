import pytest
from pydantic import BaseModel

from app.llm.base import LLMError, LLMRateLimitError, LLMUnavailableError
from app.llm.fake import FakeProvider
from app.llm.router import LLMRouter
from app.llm.tasks import ProviderName, TaskType

LOCAL_TASK = TaskType.CLASSIFY_RESPONSE
GEMINI_TASK = TaskType.ANALYZE_IDEA


class Label(BaseModel):
    label: str


def make_router(**kwargs) -> tuple[LLMRouter, FakeProvider, FakeProvider, list[float]]:
    local, gemini = FakeProvider("local"), FakeProvider("gemini")
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    router = LLMRouter(
        {ProviderName.LOCAL: local, ProviderName.GEMINI: gemini}, sleep=fake_sleep, **kwargs
    )
    return router, local, gemini, sleeps


async def test_local_task_uses_local() -> None:
    router, local, gemini, _ = make_router()
    local.queue({"label": "positive"})
    assert (await router.structured(LOCAL_TASK, "p", Label)).label == "positive"
    assert len(local.calls) == 1
    assert not gemini.calls


async def test_local_retries_invalid_output_then_succeeds() -> None:
    router, local, gemini, _ = make_router()
    local.queue("not json", {"label": "ok"})
    assert (await router.structured(LOCAL_TASK, "p", Label)).label == "ok"
    assert len(local.calls) == 2
    assert not gemini.calls


async def test_local_invalid_twice_escalates_to_gemini() -> None:
    router, local, gemini, _ = make_router()
    local.queue("nope", {"wrong": 1})
    gemini.queue({"label": "from-gemini"})
    assert (await router.structured(LOCAL_TASK, "p", Label)).label == "from-gemini"
    assert len(local.calls) == 2
    assert len(gemini.calls) == 1


async def test_local_unavailable_escalates_immediately() -> None:
    router, local, gemini, _ = make_router()
    local.queue(LLMUnavailableError("ollama down"))
    gemini.queue({"label": "g"})
    assert (await router.structured(LOCAL_TASK, "p", Label)).label == "g"
    assert len(local.calls) == 1


async def test_gemini_task_uses_gemini() -> None:
    router, local, gemini, _ = make_router()
    gemini.queue({"label": "g"})
    assert (await router.structured(GEMINI_TASK, "p", Label)).label == "g"
    assert not local.calls


async def test_gemini_invalid_output_does_not_downgrade() -> None:
    router, local, gemini, _ = make_router()
    gemini.queue("bad", "still bad")
    with pytest.raises(LLMError):
        await router.structured(GEMINI_TASK, "p", Label)
    assert not local.calls


async def test_gemini_unavailable_downgrades_to_local() -> None:
    router, local, gemini, _ = make_router()
    gemini.queue(LLMUnavailableError("no key"))
    local.queue({"label": "local"})
    assert (await router.structured(GEMINI_TASK, "p", Label)).label == "local"


async def test_downgrade_can_be_disabled() -> None:
    router, local, gemini, _ = make_router(allow_downgrade=False)
    gemini.queue(LLMUnavailableError("no key"))
    with pytest.raises(LLMError):
        await router.structured(GEMINI_TASK, "p", Label)
    assert not local.calls


async def test_rate_limit_backs_off_then_succeeds() -> None:
    router, _, gemini, sleeps = make_router()
    gemini.queue(LLMRateLimitError("429"), LLMRateLimitError("429", retry_after=7), {"label": "g"})
    assert (await router.structured(GEMINI_TASK, "p", Label)).label == "g"
    assert sleeps == [2.0, 7]


async def test_route_override() -> None:
    router, local, gemini, _ = make_router(routes={GEMINI_TASK: ProviderName.LOCAL})
    local.queue({"label": "l"})
    assert (await router.structured(GEMINI_TASK, "p", Label)).label == "l"
    assert not gemini.calls


async def test_text_generation_is_routed() -> None:
    router, local, _, _ = make_router()
    local.queue("hello")
    assert await router.text(TaskType.DRAFT_OUTREACH, "p") == "hello"
