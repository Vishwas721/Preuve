from typing import Any

from google import genai
from google.genai import errors, types

from app.llm.base import (
    LLMOutputError,
    LLMProvider,
    LLMRateLimitError,
    LLMUnavailableError,
    T,
    parse_structured,
)

# We never pass tools, so turn off the SDK's automatic function calling (and its warning).
_NO_AFC = types.AutomaticFunctionCallingConfig(disable=True)


class GeminiProvider(LLMProvider):
    """Gemini via the `google-genai` SDK (free tier). Used for heavy synthesis tasks."""

    name = "gemini"

    def __init__(self, api_key: str, model: str, *, client: Any | None = None) -> None:
        self.model = model
        self._configured = bool(api_key) or client is not None
        self._client = client or (genai.Client(api_key=api_key) if api_key else None)

    async def _generate(self, prompt: str, config: types.GenerateContentConfig) -> str:
        if self._client is None:
            raise LLMUnavailableError("Gemini not configured (GEMINI_API_KEY is empty)")
        try:
            resp = await self._client.aio.models.generate_content(
                model=self.model, contents=prompt, config=config
            )
        except errors.APIError as exc:
            if exc.code == 429:
                raise LLMRateLimitError(f"Gemini rate limited: {exc}") from exc
            raise LLMUnavailableError(f"Gemini error {exc.code}: {exc}") from exc
        text = resp.text
        if not text:
            raise LLMOutputError("Gemini returned an empty response")
        return text

    async def generate_text(
        self, prompt: str, *, system: str | None = None, temperature: float = 0.2
    ) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system, temperature=temperature, automatic_function_calling=_NO_AFC
        )
        return await self._generate(prompt, config)

    async def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        system: str | None = None,
        temperature: float = 0.0,
    ) -> T:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json",
            response_json_schema=schema.model_json_schema(),
            automatic_function_calling=_NO_AFC,
        )
        raw = await self._generate(prompt, config)
        return parse_structured(raw, schema)

    async def is_available(self) -> bool:
        return self._configured
