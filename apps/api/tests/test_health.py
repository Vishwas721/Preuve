import pytest
from httpx import ASGITransport, AsyncClient

from app.llm.fake import FakeProvider
from app.llm.router import LLMRouter
from app.llm.tasks import ProviderName
from app.main import create_app
from app.modules.meta import router as meta


async def _up() -> bool:
    return True


async def _down() -> bool:
    raise ConnectionError("down")


@pytest.fixture
def fake_router(monkeypatch: pytest.MonkeyPatch) -> None:
    llm = LLMRouter({ProviderName.LOCAL: FakeProvider(), ProviderName.GEMINI: FakeProvider()})
    monkeypatch.setattr(meta, "get_llm_router", lambda: llm)
    monkeypatch.setattr(meta, "_check_searxng", _up)


async def _get_health() -> dict:
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        resp = await c.get("/health")
    assert resp.status_code == 200
    return resp.json()


async def test_health_ok_when_required_deps_up(
    fake_router: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(meta, "_check_db", _up)
    monkeypatch.setattr(meta, "_check_redis", _up)
    body = await _get_health()
    assert body["status"] == "ok"
    assert set(body["checks"]) == {"database", "redis", "searxng", "ollama", "gemini_configured"}


async def test_health_degraded_when_db_down(
    fake_router: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(meta, "_check_db", _down)
    monkeypatch.setattr(meta, "_check_redis", _up)
    body = await _get_health()
    assert body["status"] == "degraded"
    assert body["checks"]["database"] is False
