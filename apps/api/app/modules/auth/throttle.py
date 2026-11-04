"""Failed-login throttling (Phase 5A): 5 failures per email in 15 minutes locks that email for 15.

Counters live in Redis so every API process shares them. If Redis is unreachable the check is
skipped (logged), so an outage doesn't lock everyone out; API-wide rate limiting is Phase 5C.
"""

import logging
import time
from typing import Protocol

from fastapi import Request
from redis.asyncio import Redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

MAX_FAILURES = 5
WINDOW_S = 15 * 60


class Throttle(Protocol):
    async def blocked(self, key: str) -> bool: ...
    async def fail(self, key: str) -> None: ...
    async def reset(self, key: str) -> None: ...


class RedisThrottle:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    @staticmethod
    def _k(key: str) -> str:
        return f"preuve:login-fail:{key}"

    async def blocked(self, key: str) -> bool:
        try:
            n = await self.redis.get(self._k(key))
        except Exception as exc:  # noqa: BLE001
            logger.warning("login throttle unavailable: %s", exc)
            return False
        return int(n or 0) >= MAX_FAILURES

    async def fail(self, key: str) -> None:
        try:
            k = self._k(key)
            n = await self.redis.incr(k)
            if n == 1 or n == MAX_FAILURES:  # the lock lasts a full window from the last strike
                await self.redis.expire(k, WINDOW_S)
        except Exception as exc:  # noqa: BLE001
            logger.warning("login throttle unavailable: %s", exc)

    async def reset(self, key: str) -> None:
        try:
            await self.redis.delete(self._k(key))
        except Exception as exc:  # noqa: BLE001
            logger.warning("login throttle unavailable: %s", exc)


class MemoryThrottle:
    """Single-process stand-in, used by tests."""

    def __init__(self) -> None:
        self.fails: dict[str, list[float]] = {}

    def _recent(self, key: str) -> list[float]:
        now = time.monotonic()
        self.fails[key] = [t for t in self.fails.get(key, []) if now - t < WINDOW_S]
        return self.fails[key]

    async def blocked(self, key: str) -> bool:
        return len(self._recent(key)) >= MAX_FAILURES

    async def fail(self, key: str) -> None:
        self._recent(key).append(time.monotonic())

    async def reset(self, key: str) -> None:
        self.fails.pop(key, None)


async def get_throttle(request: Request) -> Throttle:
    throttle = getattr(request.app.state, "throttle", None)
    if throttle is None:
        throttle = RedisThrottle(Redis.from_url(get_settings().redis_url))
        request.app.state.throttle = throttle
    return throttle
