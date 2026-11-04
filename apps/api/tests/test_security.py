"""Phase 5C: rate limits, security headers, size limits, secrets, email headers, reset links."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core import ratelimit
from app.core.config import DEV_OUTREACH_SECRET, Settings
from app.email.base import OutgoingEmail
from app.email.smtp import build_message
from app.modules.auth.models import PasswordReset
from tests.conftest import OWNER_EMAIL, PASSWORD, make_app, new_client

IDEA = {"title": "t", "description": "d", "target_market": "US"}


# ---------- rate limits ----------


async def test_public_auth_routes_are_rate_limited_per_ip(anon_client: AsyncClient) -> None:
    for _ in range(ratelimit.PUBLIC_AUTH[1]):
        assert (await anon_client.get("/invitations/inv_nope")).status_code == 404
    r = await anon_client.get("/invitations/inv_nope")
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1
    # status and health aren't limited: the web app calls them on every load
    assert (await anon_client.get("/auth/status")).status_code == 200


async def test_expensive_routes_have_a_tighter_limit(client: AsyncClient) -> None:
    idea = (await client.post("/ideas", json=IDEA)).json()
    limit = ratelimit.EXPENSIVE[1]
    for _ in range(limit):
        assert (await client.post(f"/ideas/{idea['id']}/reports")).status_code == 201
    r = await client.post(f"/ideas/{idea['id']}/reports")
    assert r.status_code == 429 and "retry-after" in r.headers
    assert (await client.get(f"/ideas/{idea['id']}/reports")).status_code == 200  # reads still fine


async def test_general_limit_per_caller(session_maker, queue, monkeypatch) -> None:
    monkeypatch.setattr(ratelimit, "GENERAL", ("general", 3, 60))
    c = new_client(make_app(session_maker, queue))
    await c.post("/auth/setup", json={"email": OWNER_EMAIL, "name": "F", "password": PASSWORD})
    codes = [(await c.get("/ideas")).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    await c.aclose()


def test_expensive_route_patterns() -> None:
    match = ratelimit._EXPENSIVE_POSTS.match
    for path in [
        "/ideas/x/analyze",
        "/ideas/x/research-imports",
        "/ideas/x/campaigns/y/drafts",
        "/ideas/x/campaigns/y/send",
        "/ideas/x/responses",
        "/ideas/x/responses/y/reanalyze",
        "/ideas/x/interviews/y/extract",
        "/ideas/x/reports",
        "/outreach/inbox/check",
    ]:
        assert match(path), path
    for path in ["/ideas", "/ideas/x/campaigns", "/ideas/x/interviews", "/ideas/x/experiments"]:
        assert not match(path), path


# ---------- headers, sizes, docs ----------


async def test_security_headers_on_every_response(client: AsyncClient) -> None:
    for path in ("/health", "/auth/me", "/unsubscribe/nope"):
        r = await client.get(path)
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"
        assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
        assert r.headers["referrer-policy"] == "no-referrer"
    assert (await client.get("/auth/me")).headers["cache-control"] == "no-store"
    assert "strict-transport-security" not in (await client.get("/health")).headers  # dev


async def test_oversized_requests_are_refused(client: AsyncClient) -> None:
    big = {**IDEA, "description": "x" * 6_000_000}
    r = await client.post("/ideas", json=big)
    assert r.status_code == 413
    assert (await client.post("/ideas", json=IDEA)).status_code == 201


def test_production_refuses_dev_secrets() -> None:
    with pytest.raises(ValueError, match="OUTREACH_SECRET"):
        Settings(environment="production", outreach_secret=DEV_OUTREACH_SECRET)
    with pytest.raises(ValueError, match="OUTREACH_SECRET"):
        Settings(environment="production", outreach_secret="short")
    assert Settings(environment="production", outreach_secret="x" * 40).environment == "production"
    assert Settings(environment="development", outreach_secret=DEV_OUTREACH_SECRET)


def test_api_docs_are_off_outside_development(monkeypatch) -> None:
    from app.core import config
    from app.main import create_app

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("OUTREACH_SECRET", "y" * 40)
    config.get_settings.cache_clear()
    try:
        app = create_app()
        assert app.docs_url is None and app.openapi_url is None and app.redoc_url is None
    finally:
        config.get_settings.cache_clear()


def test_line_breaks_in_header_fields_cant_break_a_send() -> None:
    msg = build_message(
        OutgoingEmail(
            from_name="Ada",
            from_address="ada@x.test",
            to_name="Jane\r\nBcc: victim@evil.test",
            to_address="jane@x.test",
            subject="Hello\nBcc: victim@evil.test",
            body="hi",
            message_id="<1@x.test>",
        )
    )
    head = msg.as_string().split("\n\n", 1)[0]
    assert "\nBcc:" not in head
    assert msg["Subject"] == "Hello Bcc: victim@evil.test"


# ---------- password-reset links ----------


async def _member(app, owner: AsyncClient, email="sam@team.test", role="owner") -> AsyncClient:
    ws = (await owner.get("/auth/me")).json()["active_workspace_id"]
    token = (
        await owner.post(f"/workspaces/{ws}/invitations", json={"email": email, "role": role})
    ).json()["token"]
    c = new_client(app)
    await c.post(f"/invitations/{token}/signup", json={"name": "Sam", "password": PASSWORD})
    return c


async def test_only_the_instance_owner_creates_reset_links(session_maker, queue) -> None:
    app = make_app(session_maker, queue)
    owner = new_client(app)
    me = (
        await owner.post(
            "/auth/setup", json={"email": OWNER_EMAIL, "name": "F", "password": PASSWORD}
        )
    ).json()
    assert me["user"]["is_instance_owner"] is True
    sam = await _member(app, owner)  # even a workspace *owner*...
    sam_id = (await sam.get("/auth/me")).json()["user"]["id"]
    assert (await sam.get("/admin/users")).status_code == 403
    assert (await sam.post(f"/admin/users/{me['user']['id']}/reset-link")).status_code == 403

    users = (await owner.get("/admin/users")).json()
    assert {u["email"] for u in users} == {OWNER_EMAIL, "sam@team.test"}
    link = await owner.post(f"/admin/users/{sam_id}/reset-link")
    assert link.status_code == 201 and link.json()["expires_in_minutes"] == 60
    token = link.json()["token"]
    async with session_maker() as s:
        assert token not in (await s.scalar(select(PasswordReset.token_hash)))

    anon = new_client(app)
    assert (await anon.get(f"/password-reset/{token}")).json() == {"email": "sam@team.test"}
    weak = await anon.post(f"/password-reset/{token}", json={"password": "short"})
    assert weak.status_code == 422
    new = "sam's brand new passphrase"
    assert (await anon.post(f"/password-reset/{token}", json={"password": new})).status_code == 204
    assert (await sam.get("/auth/me")).status_code == 401  # signed out everywhere
    assert (await anon.get(f"/password-reset/{token}")).status_code == 404  # one use
    ok = await anon.post("/auth/login", json={"email": "sam@team.test", "password": new})
    assert ok.status_code == 200
    for c in (owner, sam, anon):
        await c.aclose()


async def test_reset_links_expire(client: AsyncClient, session_maker) -> None:
    me = (await client.get("/auth/me")).json()
    token = (await client.post(f"/admin/users/{me['user']['id']}/reset-link")).json()["token"]
    async with session_maker() as s:
        row = await s.scalar(select(PasswordReset))
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await s.commit()
    assert (await client.get(f"/password-reset/{token}")).status_code == 404
    r = await client.post(f"/password-reset/{token}", json={"password": "a long new passphrase"})
    assert r.status_code == 404
