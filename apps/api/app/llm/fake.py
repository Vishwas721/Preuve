from collections import deque
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.llm.base import LLMProvider, T, parse_structured


@dataclass
class FakeCall:
    kind: str  # "text" | "structured"
    prompt: str
    system: str | None
    schema: type[BaseModel] | None = None


class FakeProvider(LLMProvider):
    """Deterministic provider for tests.

    Queue responses up front. Each item may be a model instance, a dict, a raw string (parsed
    like real model output, so invalid JSON can be simulated), or an Exception to raise.
    """

    def __init__(self, name: str = "fake", responses: list[Any] | None = None) -> None:
        self.name = name
        self.responses: deque[Any] = deque(responses or [])
        self.calls: list[FakeCall] = []

    def queue(self, *items: Any) -> None:
        self.responses.extend(items)

    def _next(self) -> Any:
        if not self.responses:
            raise AssertionError(f"FakeProvider '{self.name}' has no queued responses")
        item = self.responses.popleft()
        if isinstance(item, Exception):
            raise item
        return item

    async def generate_text(
        self, prompt: str, *, system: str | None = None, temperature: float = 0.2
    ) -> str:
        self.calls.append(FakeCall("text", prompt, system))
        return str(self._next())

    async def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        system: str | None = None,
        temperature: float = 0.0,
    ) -> T:
        self.calls.append(FakeCall("structured", prompt, system, schema))
        item = self._next()
        if isinstance(item, BaseModel):
            return schema.model_validate(item.model_dump())
        if isinstance(item, dict):
            return schema.model_validate(item)
        return parse_structured(str(item), schema)
