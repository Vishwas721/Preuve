from typing import Annotated, Any, Protocol

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import Depends, Request

from app.core.config import get_settings


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_settings().redis_url)


class JobQueue(Protocol):
    async def enqueue_job(self, function: str, *args: Any, **kwargs: Any) -> Any: ...


async def get_job_queue(request: Request) -> JobQueue:
    """arq pool shared by the API process, created on first use (closed in app lifespan).

    Lazy so the API still starts (and /health can report it) when Redis is down.
    """
    pool = getattr(request.app.state, "arq", None)
    if pool is None:
        pool = await create_pool(redis_settings())
        request.app.state.arq = pool
    return pool


QueueDep = Annotated[JobQueue, Depends(get_job_queue)]
