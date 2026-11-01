import asyncio
import logging
import time
from collections.abc import Callable, Sequence
from typing import Any

import httpx
from google import genai
from google.genai import errors, types

from app.llm.base import (
    LLMError,
    LLMOutputError,
    LLMProvider,
    LLMRateLimitError,
    LLMUnavailableError,
    T,
    parse_structured,
)

logger = logging.getLogger(__name__)

# We never pass tools, so turn off the SDK's automatic function calling (and its warning).
_NO_AFC = types.AutomaticFunctionCallingConfig(disable=True)


class GeminiProvider(LLMProvider):
    """Gemini via the `google-genai` SDK (free tier), with a model fallback chain.

    Free-tier models are individually rate limited and sometimes overloaded, so each call walks
    `models` in order:
      - 429 / 5xx / timeout / unknown model -> put that model on cooldown, try the next one;
      - invalid or empty output             -> try the next one (no cooldown).
    Models on cooldown are skipped until it expires, so one slow model doesn't stall every call.
    SDK-level retries are disabled; fallback (here) and backoff (in the router) are ours.
    """

    name = "gemini"

    def __init__(
        self,
        api_key: str,
        models: Sequence[str],
        *,
        timeout_s: float = 45.0,
        cooldown_s: float = 300.0,
        client: Any | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not models:
            raise ValueError("GeminiProvider needs at least one model")
        self.models = list(models)
        self.timeout_s = timeout_s
        self.cooldown_s = cooldown_s
        self._clock = clock
        self._cooldown_until: dict[str, float] = {}
        self._configured = bool(api_key) or client is not None
        if client is None and api_key:
            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(
                    timeout=int(timeout_s * 1000),
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
        self._client = client

    def _available_models(self) -> list[str]:
        now = self._clock()
        ready = [m for m in self.models if self._cooldown_until.get(m, 0.0) <= now]
        # If every model is cooling down, try them all anyway rather than failing outright.
        return ready or list(self.models)

    def _cool_down(self, model: str, reason: str) -> None:
        self._cooldown_until[model] = self._clock() + self.cooldown_s
        logger.warning("gemini model=%s cooling down %.0fs: %s", model, self.cooldown_s, reason)

    async def _call_model(
        self, model: str, prompt: str, config: types.GenerateContentConfig
    ) -> str:
        try:
            resp = await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=model, contents=prompt, config=config
                ),
                timeout=self.timeout_s + 5,
            )
        except errors.APIError as exc:
            if exc.code == 429:
                raise LLMRateLimitError(f"{model} rate limited: {exc}") from exc
            raise LLMUnavailableError(f"{model} error {exc.code}: {exc}") from exc
        except (TimeoutError, httpx.HTTPError) as exc:
            raise LLMUnavailableError(f"{model} timed out or unreachable: {exc!r}") from exc
        if not resp.text:
            raise LLMOutputError(f"{model} returned an empty response")
        return resp.text

    async def _generate(
        self, prompt: str, config: types.GenerateContentConfig, parse: Callable[[str], Any]
    ) -> Any:
        if self._client is None:
            raise LLMUnavailableError("Gemini not configured (GEMINI_API_KEY is empty)")

        errors_seen: list[LLMError] = []
        for model in self._available_models():
            try:
                result = parse(await self._call_model(model, prompt, config))
            except LLMOutputError as exc:
                logger.info("gemini model=%s invalid output, trying next model", model)
                errors_seen.append(exc)
            except LLMUnavailableError as exc:  # includes rate limits
                self._cool_down(model, str(exc)[:200])
                errors_seen.append(exc)
            else:
                logger.info("gemini model=%s ok", model)
                return result

        # Every model failed: surface the most actionable error type to the router.
        summary = "; ".join(str(e)[:200] for e in errors_seen)
        if any(isinstance(e, LLMOutputError) for e in errors_seen):
            raise LLMOutputError(f"All Gemini models gave invalid output: {summary}")
        if all(isinstance(e, LLMRateLimitError) for e in errors_seen):
            raise LLMRateLimitError(f"All Gemini models rate limited: {summary}")
        raise LLMUnavailableError(f"All Gemini models unavailable: {summary}")

    async def generate_text(
        self, prompt: str, *, system: str | None = None, temperature: float = 0.2
    ) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system, temperature=temperature, automatic_function_calling=_NO_AFC
        )
        return await self._generate(prompt, config, parse=lambda raw: raw)

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
        return await self._generate(prompt, config, parse=lambda raw: parse_structured(raw, schema))

    async def is_available(self) -> bool:
        return self._configured
