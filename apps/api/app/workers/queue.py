from arq import ArqRedis, create_pool
from arq.connections import RedisSettings

from app.core.config import get_settings


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_settings().redis_url)


async def get_queue() -> ArqRedis:
    """Open a pool for enqueueing jobs from the API process."""
    return await create_pool(redis_settings())
