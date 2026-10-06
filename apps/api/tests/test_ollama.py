import json

import httpx
import pytest
from pydantic import BaseModel

from app.llm.base import LLMUnavailableError
from app.llm.ollama import OllamaProvider


class Label(BaseModel):
    label: str


async def test_structured_sends_schema_and_parses() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": '{"label": "positive"}'}})

    provider = OllamaProvider("http://ollama", "llama3:8b", transport=httpx.MockTransport(handler))
    result = await provider.generate_structured("classify", Label)
    assert result.label == "positive"
    assert seen["model"] == "llama3:8b"
    assert seen["stream"] is False
    assert seen["format"]["properties"]["label"]["type"] == "string"


async def test_http_error_is_unavailable() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(404, text="model not found"))
    provider = OllamaProvider("http://ollama", "missing", transport=transport)
    with pytest.raises(LLMUnavailableError):
        await provider.generate_text("hi")


async def test_is_available_checks_model_is_pulled() -> None:
    transport = httpx.MockTransport(
        lambda r: httpx.Response(200, json={"models": [{"name": "llama3:8b"}]})
    )
    assert await OllamaProvider("http://o", "llama3:8b", transport=transport).is_available()
    assert not await OllamaProvider("http://o", "qwen2.5:7b", transport=transport).is_available()
