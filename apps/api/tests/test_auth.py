"""Phase 5A: accounts, sessions, CSRF, throttling, invitations, roles and API tokens."""

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.auth import service as auth
from app.modules.auth.models import ApiToken, AuthSession
from app.modules.auth.security import hash_token
from app.modules.auth.throttle import MAX_FAILURES, MemoryThrottle
from app.modules.ideas.models import Idea
from app.modules.ideas.schemas import IdeaCreate
from app.modules.ideas.service import create_idea
from app.modules.users.models import User
from app.modules.users.service import get_or_create_user
from app.modules.workspaces.service import personal_workspace_id
from tests.conftest import ORIGIN, OWNER_EMAIL, PASSWORD, make_app, new_client

IDEA = {"title": "t", "description": "d", "target_market": "US"}


async def _invite(owner: AsyncClient, email: str, role: str = "member") -> str:
    ws = (await owner.get("/auth/me")).json()["active_workspace_id"]
    r = await owner.post(f"/workspaces/{ws}/invitations", json={"email": email, "role": role})
    assert r.status_code == 201, r.text
    return r.json()["token"]


async def _second_user(app, owner: AsyncClient, email: str = "sam@team.test", role="member"):
    token = await _invite(owner, email, role)
    c = new_client(app)
    r = await c.post(f"/invitations/{token}/signup", json={"name": "Sam", "password": PASSWORD})
    assert r.status_code == 201, r.text
    return c


# ---------- setup ----------


async def test_setup_claims_existing_dev_data(
    anon_client: AsyncClient, session_maker: async_sessionmaker[AsyncSession]
) -> None:
    async with session_maker() as s:  # pre-5A data: the dev user and their idea
        dev = await get_or_create_user(s, OWNER_EMAIL, "Founder")
        await create_idea(s, await personal_workspace_id(s, dev), IdeaCreate(**IDEA))

    status = (await anon_client.get("/auth/status")).json()
    assert status == {"needs_setup": True, "signup_open": False, "signed_in": False}
    r = await anon_client.post(
        "/auth/setup", json={"email": "Me@Example.com", "name": "Me", "password": PASSWORD}
    )
    assert r.status_code == 201, r.text
    assert r.json()["user"]["email"] == "me@example.com"  # the dev user, renamed
    assert [i["title"] for i in (await anon_client.get("/ideas")).json()] == ["t"]

    again = await anon_client.post(
        "/auth/setup", json={"email": "x@y.test", "name": "X", "password": PASSWORD}
    )
    assert again.status_code == 409
    assert (await anon_client.get("/auth/status")).json()["needs_setup"] is False


async def test_weak_passwords_are_refused(anon_client: AsyncClient) -> None:
    for pw in ("short", "1234567890", "aaaaaaaaaaaa", "founder-secret-1"):
        r = await anon_client.post(
            "/auth/setup", json={"email": "founder@x.test", "name": "F", "password": pw}
        )
        assert r.status_code == 422, pw


# ---------- sessions ----------


async def test_password_is_hashed_and_session_cookie_is_safe(
    anon_client: AsyncClient, session_maker
) -> None:
    r = await anon_client.post(
        "/auth/setup", json={"email": OWNER_EMAIL, "name": "F", "password": PASSWORD}
    )
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie
    raw = anon_client.cookies["preuve_session"]
    async with session_maker() as s:
        user = await s.scalar(select(User).where(User.email == OWNER_EMAIL))
        assert user.password_hash.startswith("$argon2id$") and PASSWORD not in user.password_hash
        stored = await s.scalar(select(AuthSession.token_hash))
        assert stored == hash_token(raw) and raw not in stored


async def test_login_logout_and_unauthenticated(client: AsyncClient, anon_client) -> None:
    assert (await anon_client.get("/ideas")).status_code == 401
    me = (await client.get("/auth/me")).json()
    assert me["user"]["email"] == OWNER_EMAIL and me["via"] == "session"
    assert me["workspaces"][0]["role"] == "owner"

    assert (await client.post("/auth/logout")).status_code == 204
    assert (await client.get("/ideas")).status_code == 401

    bad = await client.post(
        "/auth/login", json={"email": OWNER_EMAIL, "password": "nope-nope-nope"}
    )
    unknown = await client.post("/auth/login", json={"email": "who@x.test", "password": PASSWORD})
    assert bad.status_code == unknown.status_code == 401
    assert bad.json() == unknown.json() == {"detail": auth.GENERIC_LOGIN_ERROR}
    ok = await client.post(
        "/auth/login", json={"email": " Founder@Preuve.local ", "password": PASSWORD}
    )
    assert ok.status_code == 200 and (await client.get("/ideas")).status_code == 200


async def test_expired_session_is_refused(client: AsyncClient, session_maker) -> None:
    from datetime import UTC, datetime, timedelta

    async with session_maker() as s:
        row = await s.scalar(select(AuthSession))
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await s.commit()
    assert (await client.get("/auth/me")).status_code == 401


async def test_password_change_ends_other_sessions(
    session_maker, queue, client: AsyncClient
) -> None:
    other = new_client(make_app(session_maker, queue))
    await other.post("/auth/login", json={"email": OWNER_EMAIL, "password": PASSWORD})
    assert (await other.get("/auth/me")).status_code == 200

    new = "a much better passphrase"
    wrong = await client.post("/auth/password", json={"current": "wrong-one-x", "new": new})
    assert wrong.status_code == 400
    r = await client.post("/auth/password", json={"current": PASSWORD, "new": new})
    assert r.status_code == 204
    assert (await client.get("/auth/me")).status_code == 200  # this one stays
    assert (await other.get("/auth/me")).status_code == 401  # the other is gone
    await other.aclose()


async def test_failed_logins_are_throttled(session_maker, queue, client: AsyncClient) -> None:
    throttle = MemoryThrottle()
    c = new_client(make_app(session_maker, queue, throttle))
    for _ in range(MAX_FAILURES):
        r = await c.post("/auth/login", json={"email": OWNER_EMAIL, "password": "wrong-password"})
        assert r.status_code == 401
    r = await c.post("/auth/login", json={"email": OWNER_EMAIL, "password": PASSWORD})
    assert r.status_code == 429  # even the right password, until the window passes
    await throttle.reset(OWNER_EMAIL)
    r = await c.post("/auth/login", json={"email": OWNER_EMAIL, "password": PASSWORD})
    assert r.status_code == 200
    await c.aclose()


async def test_cookie_writes_need_an_allowed_origin(client: AsyncClient) -> None:
    r = await client.post("/ideas", json=IDEA, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = await client.post("/ideas", json=IDEA, headers={"Origin": "", "Referer": ""})
    assert r.status_code == 403  # no origin at all
    r = await client.post("/ideas", json=IDEA, headers={"Referer": f"{ORIGIN}/ideas/new"})
    assert r.status_code == 201
    assert (
        await client.get("/ideas", headers={"Origin": "https://evil.example"})
    ).status_code == 200


# ---------- workspaces, invitations, roles ----------


async def test_invite_signup_roles_and_removal(session_maker, queue) -> None:
    app = make_app(session_maker, queue)
    owner = new_client(app)
    await owner.post("/auth/setup", json={"email": OWNER_EMAIL, "name": "F", "password": PASSWORD})
    ws = (await owner.get("/auth/me")).json()["active_workspace_id"]
    idea = (await owner.post("/ideas", json=IDEA)).json()

    token = await _invite(owner, "sam@team.test")
    anon = new_client(app)
    info = (await anon.get(f"/invitations/{token}")).json()
    assert info["email"] == "sam@team.test" and info["role"] == "member"
    assert info["account_exists"] is False
    sam = await anon.post(
        f"/invitations/{token}/signup", json={"name": "Sam", "password": PASSWORD}
    )
    assert sam.status_code == 201 and sam.json()["active_workspace_id"] == ws
    assert (await anon.get(f"/invitations/{token}")).status_code == 404  # used up

    # A member works on ideas but can't manage the workspace.
    assert (await anon.get(f"/ideas/{idea['id']}")).status_code == 200
    assert (
        await anon.post(f"/workspaces/{ws}/invitations", json={"email": "z@z.test"})
    ).status_code == 403
    assert (await anon.patch(f"/workspaces/{ws}", json={"name": "mine"})).status_code == 403
    members = (await anon.get(f"/workspaces/{ws}/members")).json()
    assert {m["email"]: m["role"] for m in members} == {
        OWNER_EMAIL: "owner",
        "sam@team.test": "member",
    }

    # The last owner can't be demoted or removed.
    owner_id = next(m["user_id"] for m in members if m["role"] == "owner")
    r = await owner.patch(f"/workspaces/{ws}/members/{owner_id}", json={"role": "member"})
    assert r.status_code == 409

    # Removal ends access on the very next request.
    sam_id = next(m["user_id"] for m in members if m["role"] == "member")
    assert (await owner.delete(f"/workspaces/{ws}/members/{sam_id}")).status_code == 204
    assert (await anon.get(f"/ideas/{idea['id']}")).status_code == 404
    await owner.aclose()
    await anon.aclose()


async def test_invitation_for_another_email_cant_be_accepted(session_maker, queue) -> None:
    app = make_app(session_maker, queue)
    owner = new_client(app)
    await owner.post("/auth/setup", json={"email": OWNER_EMAIL, "name": "F", "password": PASSWORD})
    sam = await _second_user(app, owner)
    token = await _invite(owner, "someone-else@team.test")
    assert (await sam.post(f"/invitations/{token}/accept")).status_code == 403
    ws = (await owner.get("/auth/me")).json()["active_workspace_id"]
    revoked = await _invite(owner, "late@team.test")
    inv = [
        i
        for i in (await owner.get(f"/workspaces/{ws}/invitations")).json()
        if i["email"] == "late@team.test"
    ]
    assert (await owner.delete(f"/workspaces/{ws}/invitations/{inv[0]['id']}")).status_code == 204
    assert (await sam.get(f"/invitations/{revoked}")).status_code == 404
    await owner.aclose()
    await sam.aclose()


async def test_switching_workspaces_scopes_the_idea_list(client: AsyncClient) -> None:
    await client.post("/ideas", json=IDEA | {"title": "home"})
    ws = (await client.post("/workspaces", json={"name": "Side project"})).json()
    me = (await client.post("/auth/workspace", json={"workspace_id": ws["id"]})).json()
    assert me["active_workspace_id"] == ws["id"] and len(me["workspaces"]) == 2
    assert (await client.get("/ideas")).json() == []
    await client.post("/ideas", json=IDEA | {"title": "side"})
    assert [i["title"] for i in (await client.get("/ideas")).json()] == ["side"]
    assert [i["title"] for i in (await client.get("/portfolio")).json()] == ["side"]


# ---------- API tokens ----------


async def test_api_token_is_bound_to_one_workspace(
    client: AsyncClient, session_maker, queue
) -> None:
    home = (await client.post("/ideas", json=IDEA | {"title": "home"})).json()
    r = await client.post("/auth/tokens", json={"name": "research CLI"})
    assert r.status_code == 201
    raw = r.json()["token"]
    assert raw.startswith("prv_") and r.json()["token_prefix"] == raw[:12]
    async with session_maker() as s:
        stored = await s.scalar(select(ApiToken.token_hash))
        assert stored == hash_token(raw)
    assert "token" not in (await client.get("/auth/tokens")).json()[0]

    side = (await client.post("/workspaces", json={"name": "Side"})).json()
    await client.post("/auth/workspace", json={"workspace_id": side["id"]})
    side_idea = (await client.post("/ideas", json=IDEA | {"title": "side"})).json()

    bot = new_client(make_app(session_maker, queue))
    bot.headers.pop("Origin")  # scripts send no Origin; bearer requests don't need one
    h = {"Authorization": f"Bearer {raw}"}
    assert [i["title"] for i in (await bot.get("/ideas", headers=h)).json()] == ["home"]
    assert (await bot.post("/ideas", json=IDEA, headers=h)).status_code == 201
    assert (await bot.get(f"/ideas/{side_idea['id']}", headers=h)).status_code == 404
    assert (await bot.get(f"/ideas/{home['id']}", headers=h)).status_code == 200
    assert (await bot.post("/auth/tokens", json={"name": "x"}, headers=h)).status_code == 403
    me = (await bot.get("/auth/me", headers=h)).json()
    assert me["via"] == "token" and [w["name"] for w in me["workspaces"]] == ["Founder's workspace"]

    tid = (await client.get("/auth/tokens")).json()[0]["id"]
    assert (await client.delete(f"/auth/tokens/{tid}")).status_code == 204
    assert (await bot.get("/ideas", headers=h)).status_code == 401
    assert (
        await bot.get("/ideas", headers={"Authorization": "Bearer prv_nope"})
    ).status_code == 401
    await bot.aclose()


# ---------- suppressions ----------


async def test_suppressions_block_globally_but_list_per_workspace(session_maker, queue) -> None:
    from app.modules.outreach import service as outreach

    app = make_app(session_maker, queue)
    owner = new_client(app)
    await owner.post("/auth/setup", json={"email": OWNER_EMAIL, "name": "F", "password": PASSWORD})
    sam = await _second_user(app, owner)
    other_ws = (await sam.post("/workspaces", json={"name": "Sam's other"})).json()
    await sam.post("/auth/workspace", json={"workspace_id": other_ws["id"]})

    r = await owner.post("/suppressions", json={"email": "no@x.test"})
    assert r.status_code == 201 and r.json()["blocked_elsewhere"] is False
    assert (await sam.get("/suppressions")).json() == []  # not visible elsewhere
    r = await sam.post("/suppressions", json={"email": "no@x.test"})
    assert r.status_code == 201 and r.json()["blocked_elsewhere"] is True
    assert (await sam.delete(f"/suppressions/{r.json()['id']}")).status_code == 204
    async with session_maker() as s:
        assert await outreach.is_suppressed(s, "NO@x.test")  # still blocked by the owner's row
        n = await s.scalar(select(func.count()).select_from(Idea))
        assert n == 0
    await owner.aclose()
    await sam.aclose()
