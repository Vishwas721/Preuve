"""Request dependencies: the DB session and the authenticated caller (Phase 5A).

A caller is either a browser with a session cookie or a script with an API token
(`Authorization: Bearer prv_…`). Cookie requests that change state must come from an allowed
origin (CSRF); bearer requests carry no ambient credentials, so they're exempt.
"""

import uuid
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session
from app.modules.auth import service as auth
from app.modules.auth.service import Principal
from app.modules.users.models import User

SessionDep = Annotated[AsyncSession, Depends(get_session)]

SESSION_COOKIE = "preuve_session"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _origin(request: Request) -> str | None:
    origin = request.headers.get("origin")
    if origin:
        return origin.rstrip("/")
    referer = request.headers.get("referer")
    if referer:
        parts = urlsplit(referer)
        return f"{parts.scheme}://{parts.netloc}"
    return None


def check_origin(request: Request) -> None:
    """CSRF: a cookie-authenticated, state-changing request must come from the web app."""
    if request.method in _SAFE_METHODS:
        return
    allowed = {o.rstrip("/") for o in get_settings().cors_origins}
    if _origin(request) not in allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Request origin not allowed")


def _unauthorized() -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Sign in required", headers={"WWW-Authenticate": "Bearer"}
    )


async def get_principal(request: Request, session: SessionDep) -> Principal:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        principal = await auth.resolve_token(session, header[7:].strip())
        if principal is None:
            raise _unauthorized()
        return principal
    cookie = request.cookies.get(SESSION_COOKIE)
    if not cookie:
        raise _unauthorized()
    principal = await auth.resolve_session(session, cookie)
    if principal is None:
        raise _unauthorized()
    check_origin(request)
    return principal


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


async def get_current_user(principal: CurrentPrincipal) -> User:
    return principal.user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_workspace_id(principal: CurrentPrincipal) -> uuid.UUID:
    """The caller's active workspace (a session's choice, or the token's workspace)."""
    if principal.workspace_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "You don't belong to any workspace")
    return principal.workspace_id


ActiveWorkspace = Annotated[uuid.UUID, Depends(get_workspace_id)]
