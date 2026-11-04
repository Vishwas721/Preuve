import os
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.ratelimit import MemoryLimiter, get_limiter
from app.db.models import Base
from app.db.session import get_session
from app.main import create_app
from app.modules.auth.throttle import MemoryThrottle, get_throttle
from app.workers.queue import get_job_queue

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://preuve:preuve@127.0.0.1:5435/preuve_test"
)


async def _ensure_database(url: str) -> None:
    parsed = make_url(url)
    conn = await asyncpg.connect(
        user=parsed.username,
        password=parsed.password,
        host=parsed.host,
        port=parsed.port,
        database="postgres",
    )
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", parsed.database
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{parsed.database}"')
    finally:
        await conn.close()


@pytest.fixture
async def session_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    await _ensure_database(TEST_DATABASE_URL)
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


class FakeQueue:
    """Records enqueued jobs instead of talking to Redis. Set `fail` to simulate Redis down."""

    def __init__(self) -> None:
        self.jobs: list[tuple[str, tuple[Any, ...]]] = []
        self.fail = False

    async def enqueue_job(self, function: str, *args: Any, **kwargs: Any) -> None:
        if self.fail:
            raise ConnectionError("redis down")
        self.jobs.append((function, args))


@pytest.fixture
def queue() -> FakeQueue:
    return FakeQueue()


@pytest.fixture
async def session(
    session_maker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_maker() as s:
        yield s


# Every API test runs as a signed-in user through the real session path (Phase 5A).
ORIGIN = "http://localhost:3000"  # in the default CORS_ORIGINS, so cookie writes pass CSRF
PASSWORD = "correct horse battery"
OWNER_EMAIL = "founder@preuve.local"  # DEV_USER_EMAIL: setup claims it


def make_app(session_maker: async_sessionmaker[AsyncSession], queue: "FakeQueue", throttle=None):
    app = create_app()
    app.dependency_overrides[get_job_queue] = lambda: queue
    shared = throttle or MemoryThrottle()
    app.dependency_overrides[get_throttle] = lambda: shared
    limiter = MemoryLimiter()
    app.dependency_overrides[get_limiter] = lambda: limiter

    async def _session() -> AsyncIterator[AsyncSession]:
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = _session
    return app


def new_client(app) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers={"Origin": ORIGIN}
    )


@pytest.fixture
async def anon_client(
    session_maker: async_sessionmaker[AsyncSession], queue: FakeQueue
) -> AsyncIterator[AsyncClient]:
    async with new_client(make_app(session_maker, queue)) as c:
        yield c


@pytest.fixture
async def client(
    session_maker: async_sessionmaker[AsyncSession], queue: FakeQueue
) -> AsyncIterator[AsyncClient]:
    async with new_client(make_app(session_maker, queue)) as c:
        r = await c.post(
            "/auth/setup", json={"email": OWNER_EMAIL, "name": "Founder", "password": PASSWORD}
        )
        assert r.status_code == 201, r.text
        yield c
