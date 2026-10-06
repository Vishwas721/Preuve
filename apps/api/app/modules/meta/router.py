import asyncio
from collections.abc import Awaitable

import httpx
from fastapi import APIRouter
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine
from app.llm.router import get_llm_router
from app.llm.tasks import ProviderName

router = APIRouter(tags=["meta"])

CHECK_TIMEOUT_S = 3.0


class HealthStatus(BaseModel):
    status: str  # "ok" when required deps are up, otherwise "degraded"
    checks: dict[str, bool]


async def _check_db() -> bool:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True


async def _check_redis() -> bool:
    client = Redis.from_url(get_settings().redis_url)
    try:
        return bool(await client.ping())
    finally:
        await client.aclose()


async def _check_searxng() -> bool:
    async with httpx.AsyncClient(timeout=CHECK_TIMEOUT_S) as client:
        resp = await client.get(f"{get_settings().searxng_url}/healthz")
        return resp.status_code == 200


async def _safe(check: Awaitable[bool]) -> bool:
    try:
        return await asyncio.wait_for(check, CHECK_TIMEOUT_S)
    except Exception:
        return False


@router.get("/health", response_model=HealthStatus)
async def health() -> HealthStatus:
    providers = get_llm_router().providers
    names = ["database", "redis", "searxng", "ollama", "gemini_configured"]
    results = await asyncio.gather(
        _safe(_check_db()),
        _safe(_check_redis()),
        _safe(_check_searxng()),
        _safe(providers[ProviderName.LOCAL].is_available()),
        _safe(providers[ProviderName.GEMINI].is_available()),
    )
    checks = dict(zip(names, results, strict=True))
    required_ok = checks["database"] and checks["redis"]
    return HealthStatus(status="ok" if required_ok else "degraded", checks=checks)
