import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from functools import lru_cache
from typing import TypeVar

from app.core.config import get_settings
from app.llm.base import (
    LLMError,
    LLMOutputError,
    LLMProvider,
    LLMRateLimitError,
    LLMUnavailableError,
    T,
)
from app.llm.gemini import GeminiProvider
from app.llm.ollama import OllamaProvider
from app.llm.tasks import DEFAULT_ROUTES, ProviderName, TaskType

logger = logging.getLogger(__name__)

R = TypeVar("R")


class LLMRouter:
    """Routes each task to a provider, validates output, retries, and escalates.

    Provider order for a task:
      - routed LOCAL  -> local, then gemini (escalate when local output is invalid or local is down)
      - routed GEMINI -> gemini, then local only if `allow_downgrade` and gemini is *unavailable*
                         (e.g. no API key) — never because gemini's output was invalid.
    Each provider gets `max_attempts` tries on invalid output; rate limits back off and retry.
    """

    def __init__(
        self,
        providers: Mapping[ProviderName, LLMProvider],
        routes: Mapping[TaskType, ProviderName] | None = None,
        *,
        max_attempts: int = 2,
        rate_limit_retries: int = 2,
        allow_downgrade: bool = True,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.providers = dict(providers)
        self.routes = {**DEFAULT_ROUTES, **(routes or {})}
        self.max_attempts = max_attempts
        self.rate_limit_retries = rate_limit_retries
        self.allow_downgrade = allow_downgrade
        self._sleep = sleep

    def chain(self, task: TaskType) -> list[ProviderName]:
        if self.routes[task] == ProviderName.LOCAL:
            names = [ProviderName.LOCAL, ProviderName.GEMINI]
        else:
            names = [ProviderName.GEMINI]
            if self.allow_downgrade:
                names.append(ProviderName.LOCAL)
        return [n for n in names if n in self.providers]

    async def structured(
        self,
        task: TaskType,
        prompt: str,
        schema: type[T],
        *,
        system: str | None = None,
        temperature: float = 0.0,
    ) -> T:
        return await self._run(
            task,
            lambda p: p.generate_structured(prompt, schema, system=system, temperature=temperature),
        )

    async def text(
        self, task: TaskType, prompt: str, *, system: str | None = None, temperature: float = 0.2
    ) -> str:
        return await self._run(
            task, lambda p: p.generate_text(prompt, system=system, temperature=temperature)
        )

    async def _run(self, task: TaskType, call: Callable[[LLMProvider], Awaitable[R]]) -> R:
        primary = self.routes[task]
        last_error: Exception | None = None

        for name in self.chain(task):
            if name != primary and primary == ProviderName.GEMINI:
                if not isinstance(last_error, LLMUnavailableError):
                    break
                logger.warning("llm task=%s downgrading to local: %s", task, last_error)

            provider = self.providers[name]
            attempts = 0
            rate_limited = 0
            while attempts < self.max_attempts:
                started = time.perf_counter()
                try:
                    result = await call(provider)
                except LLMRateLimitError as exc:
                    last_error = exc
                    if rate_limited >= self.rate_limit_retries:
                        self._log(task, name, started, "rate_limited, giving up")
                        break
                    rate_limited += 1
                    delay = exc.retry_after or 2.0**rate_limited
                    self._log(task, name, started, f"rate_limited, retry in {delay:.0f}s")
                    await self._sleep(delay)
                except LLMUnavailableError as exc:
                    last_error = exc
                    self._log(task, name, started, f"unavailable: {exc}")
                    break
                except LLMOutputError as exc:
                    last_error = exc
                    attempts += 1
                    self._log(task, name, started, f"invalid_output (attempt {attempts})")
                else:
                    self._log(task, name, started, "ok")
                    return result

        raise LLMError(f"All providers failed for task '{task}': {last_error}") from last_error

    @staticmethod
    def _log(task: TaskType, provider: ProviderName, started: float, outcome: str) -> None:
        ms = (time.perf_counter() - started) * 1000
        logger.info("llm task=%s provider=%s ms=%.0f outcome=%s", task, provider, ms, outcome)


@lru_cache
def get_llm_router() -> LLMRouter:
    s = get_settings()
    providers: dict[ProviderName, LLMProvider] = {
        ProviderName.LOCAL: OllamaProvider(
            s.ollama_url, s.ollama_model, num_ctx=s.ollama_num_ctx, timeout_s=s.ollama_timeout_s
        ),
        ProviderName.GEMINI: GeminiProvider(s.gemini_api_key, s.gemini_model),
    }
    routes = {TaskType(k): ProviderName(v) for k, v in s.llm_route_overrides.items()}
    return LLMRouter(providers, routes, allow_downgrade=s.llm_allow_downgrade)
