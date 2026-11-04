"""Rate limits (Phase 5C): fixed windows in Redis, per caller or per client IP.

All limits live here, keyed by path pattern, so they can be read and audited in one place:

- every signed-in request: 600 / minute per caller (user or API token);
- expensive requests (LLM work or background jobs): 30 / 10 minutes per caller;
- public sign-in / sign-up / invitation / reset requests: 30 / minute per IP;
- unsubscribe pages: 60 / minute per IP.

If Redis is unreachable, limits are skipped (logged) rather than locking everyone out.
"""

import logging
import re
import time
from typing import Annotated, Protocol

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.deps import CurrentPrincipal

logger = logging.getLogger(__name__)

GENERAL = ("general", 600, 60)
EXPENSIVE = ("expensive", 30, 600)
PUBLIC_AUTH = ("public-auth", 30, 60)
UNSUBSCRIBE = ("unsubscribe", 60, 60)

_EXPENSIVE_POSTS = re.compile(
    r"^/ideas/[^/]+/("
    r"analyze|icps/generate|research-imports|campaigns/[^/]+/(drafts|send)|messages/[^/]+/redraft"
    r"|responses|responses/[^/]+/reanalyze|interviews/[^/]+/(guide|extract)|reports"
    r")$"
    r"|^/outreach/inbox/check$"
)
_PUBLIC_AUTH = re.compile(
    r"^/auth/(setup|signup|login)$|^/invitations/[^/]+(/signup)?$|^/password-reset/[^/]+$"
)
_UNSUBSCRIBE = re.compile(r"^/unsubscribe/")


class Limiter(Protocol):
    async def hit(self, key: str, limit: int, window_s: int) -> int | None:
        """Count one request; return seconds to wait if over the limit, else None."""


class RedisLimiter:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def hit(self, key: str, limit: int, window_s: int) -> int | None:
        now = time.time()
        bucket = int(now // window_s)
        k = f"preuve:rl:{key}:{bucket}"
        try:
            n = await self.redis.incr(k)
            if n == 1:
                await self.redis.expire(k, window_s + 1)
        except Exception as exc:  # noqa: BLE001
            logger.warning("rate limiter unavailable: %s", exc)
            return None
        if n > limit:
            return max(1, int(window_s - now % window_s))
        return None


class MemoryLimiter:
    """Single-process stand-in, used by tests."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    async def hit(self, key: str, limit: int, window_s: int) -> int | None:
        now = time.time()
        k = f"{key}:{int(now // window_s)}"
        self.counts[k] = self.counts.get(k, 0) + 1
        if self.counts[k] > limit:
            return max(1, int(window_s - now % window_s))
        return None


async def get_limiter(request: Request) -> Limiter:
    limiter = getattr(request.app.state, "limiter", None)
    if limiter is None:
        limiter = RedisLimiter(Redis.from_url(get_settings().redis_url))
        request.app.state.limiter = limiter
    return limiter


def client_ip(request: Request) -> str:
    """The socket address, or the proxy's client IP when TRUST_PROXY_HEADERS is set (5D)."""
    if get_settings().trust_proxy_headers:
        cf = request.headers.get("cf-connecting-ip")
        if cf:
            return cf.strip()
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


LimiterDep = Annotated[Limiter, Depends(get_limiter)]


async def _enforce(limiter: Limiter, rule: tuple[str, int, int], ident: str) -> None:
    name, limit, window = rule
    wait = await limiter.hit(f"{name}:{ident}", limit, window)
    if wait is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many requests. Slow down and try again shortly.",
            headers={"Retry-After": str(wait)},
        )


async def limit_private(request: Request, principal: CurrentPrincipal, limiter: LimiterDep) -> None:
    who = f"token:{principal.token.id}" if principal.token else f"user:{principal.user.id}"
    await _enforce(limiter, GENERAL, who)
    if request.method == "POST" and _EXPENSIVE_POSTS.match(request.url.path):
        await _enforce(limiter, EXPENSIVE, who)


async def limit_public(request: Request, limiter: LimiterDep) -> None:
    path = request.url.path
    if _UNSUBSCRIBE.match(path):
        await _enforce(limiter, UNSUBSCRIBE, client_ip(request))
    elif _PUBLIC_AUTH.match(path):
        await _enforce(limiter, PUBLIC_AUTH, client_ip(request))
