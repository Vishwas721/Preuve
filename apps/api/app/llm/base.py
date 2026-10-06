import json
import re
from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Base class for LLM failures."""


class LLMUnavailableError(LLMError):
    """Provider not configured, unreachable, or erroring."""


class LLMRateLimitError(LLMUnavailableError):
    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LLMOutputError(LLMError):
    """Provider answered, but the output didn't match the requested schema."""

    def __init__(self, message: str, raw: str = "") -> None:
        super().__init__(message)
        self.raw = raw


_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def parse_structured(raw: str, schema: type[T]) -> T:
    """Parse model output into `schema`, tolerating a surrounding ```json fence."""
    match = _FENCE.match(raw)
    text = match.group(1) if match else raw
    try:
        return schema.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise LLMOutputError(f"Output does not match {schema.__name__}: {exc}", raw=raw) from exc


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def generate_text(
        self, prompt: str, *, system: str | None = None, temperature: float = 0.2
    ) -> str: ...

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        system: str | None = None,
        temperature: float = 0.0,
    ) -> T:
        """Return an instance of `schema`, or raise LLMOutputError / LLMUnavailableError."""

    async def is_available(self) -> bool:
        return True
