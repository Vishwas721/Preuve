"""Phase 5A: the research CLI sends an API token; the owner can reset a password."""

import pytest
from sqlalchemy import select

from app.modules.auth import service as auth
from app.modules.auth.models import AuthSession
from app.modules.users.service import get_or_create_user
from app.scripts import research


class _Resp:
    status_code = 200
    content = b"{}"

    def json(self):
        return {}


def test_research_cli_sends_the_token(monkeypatch) -> None:
    seen = {}

    def fake_request(method, url, **kwargs):
        seen.update(kwargs.get("headers", {}))
        return _Resp()

    monkeypatch.setattr(research.httpx, "request", fake_request)
    monkeypatch.setenv("PREUVE_API_TOKEN", "prv_abc")
    research._api("GET", "/ideas")
    assert seen == {"Authorization": "Bearer prv_abc"}


def test_research_cli_explains_a_missing_token(monkeypatch) -> None:
    monkeypatch.delenv("PREUVE_API_TOKEN", raising=False)
    with pytest.raises(SystemExit) as exc:
        research._api("GET", "/ideas")
    assert "PREUVE_API_TOKEN" in str(exc.value)


def test_research_cli_explains_a_refused_token(monkeypatch) -> None:
    class Refused(_Resp):
        status_code = 401

    monkeypatch.setattr(research.httpx, "request", lambda *a, **k: Refused())
    monkeypatch.setenv("PREUVE_API_TOKEN", "prv_old")
    with pytest.raises(SystemExit) as exc:
        research._api("GET", "/ideas")
    assert "refused the token" in str(exc.value)


async def test_admin_password_reset_ends_sessions(session) -> None:
    user = await get_or_create_user(session, "a@b.test", "A")
    await auth.start_session(session, user)
    with pytest.raises(auth.AuthError):
        await auth.set_password(session, "nobody@b.test", "a fine long passphrase")
    await auth.set_password(session, "A@B.test", "a fine long passphrase")
    assert await session.scalar(select(AuthSession.id)) is None
    await session.refresh(user)
    assert user.password_hash.startswith("$argon2id$")
