"""Phase 5A tenant isolation: every route, walked from outside the workspace."""

import re
import uuid

from app.main import PUBLIC_ROUTERS
from tests.conftest import OWNER_EMAIL, PASSWORD, make_app, new_client

IDEA = {"title": "secret", "description": "d", "target_market": "US"}
PUBLIC_PATHS = {r.path for router in PUBLIC_ROUTERS for r in router.routes}


def _routes(app) -> list[tuple[str, str]]:
    """Every (method, path) the app serves, from its OpenAPI schema (included routers are
    resolved lazily in this FastAPI, so `app.routes` doesn't list them)."""
    return [
        (m.upper(), path)
        for path, ops in app.openapi()["paths"].items()
        for m in ops
        if m in {"get", "post", "put", "patch", "delete"}
    ]


def _fill(path: str, idea_id: str) -> str:
    path = path.replace("{idea_id}", idea_id)
    return re.sub(r"\{[a-z_]+\}", str(uuid.uuid4()), path)


async def _two_tenants(session_maker, queue):
    app = make_app(session_maker, queue)
    owner = new_client(app)
    await owner.post("/auth/setup", json={"email": OWNER_EMAIL, "name": "F", "password": PASSWORD})
    idea = (await owner.post("/ideas", json=IDEA)).json()
    # A second, unrelated account with its own workspace (invited elsewhere, then removed).
    ws = (await owner.get("/auth/me")).json()["active_workspace_id"]
    token = (
        await owner.post(f"/workspaces/{ws}/invitations", json={"email": "out@sider.test"})
    ).json()["token"]
    outsider = new_client(app)
    await outsider.post(f"/invitations/{token}/signup", json={"name": "O", "password": PASSWORD})
    me = (await outsider.get("/auth/me")).json()
    own = next(w["id"] for w in me["workspaces"] if w["id"] != ws)
    await outsider.post("/auth/workspace", json={"workspace_id": own})
    await owner.delete(f"/workspaces/{ws}/members/{me['user']['id']}")
    return app, owner, outsider, idea


async def test_every_idea_route_is_404_for_other_workspaces(session_maker, queue) -> None:
    app, owner, outsider, idea = await _two_tenants(session_maker, queue)
    checked = 0
    leaks = []
    for method, path in _routes(app):
        if "{idea_id}" not in path:
            continue
        url = _fill(path, idea["id"])
        r = await outsider.request(method, url, json={})
        checked += 1
        if r.status_code != 404:
            leaks.append(f"{method} {path} -> {r.status_code}")
    assert checked > 60, checked  # sanity: the walk really covered the idea routes
    assert leaks == []
    # ...while the owner still sees it.
    assert (await owner.get(f"/ideas/{idea['id']}")).status_code == 200
    assert [i["id"] for i in (await outsider.get("/ideas")).json()] == []
    assert (await outsider.get("/portfolio")).json() == []


async def test_reports_by_id_are_404_for_other_workspaces(session_maker, queue) -> None:
    _, owner, outsider, idea = await _two_tenants(session_maker, queue)
    rid = (await owner.post(f"/ideas/{idea['id']}/reports")).json()["id"]
    for method, url in [
        ("GET", f"/reports/{rid}"),
        ("GET", f"/reports/{rid}/markdown"),
        ("DELETE", f"/reports/{rid}"),
    ]:
        assert (await outsider.request(method, url)).status_code == 404, url
    assert (await owner.get(f"/reports/{rid}")).status_code == 200


async def test_every_private_route_needs_sign_in(anon_client) -> None:
    app_routes = _routes(anon_client._transport.app)  # noqa: SLF001
    open_ = []
    for method, path in app_routes:
        if path in PUBLIC_PATHS or path.startswith(("/docs", "/openapi", "/redoc")):
            continue
        r = await anon_client.request(method, _fill(path, str(uuid.uuid4())), json={})
        if r.status_code != 401:
            open_.append(f"{method} {path} -> {r.status_code}")
    assert len(app_routes) > 80, len(app_routes)  # sanity: the walk covered the app
    assert open_ == []


def test_public_routes_are_only_the_expected_ones() -> None:
    assert {
        "/health",
        "/unsubscribe/{token}",
        "/auth/status",
        "/auth/setup",
        "/auth/signup",
        "/auth/login",
        "/auth/logout",
        "/invitations/{token}",
        "/invitations/{token}/signup",
        "/password-reset/{token}",  # 5C: opening and using a reset link
    } == PUBLIC_PATHS
