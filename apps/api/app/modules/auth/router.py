"""Sign-in, sessions, workspace switching and API tokens (Phase 5A).

`public_router` endpoints work without a session (status, setup, login, logout, sign-up).
Everything on `router` requires a signed-in caller.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.config import get_settings
from app.core.deps import SESSION_COOKIE, CurrentPrincipal, SessionDep, check_origin
from app.modules.auth import service
from app.modules.auth.schemas import (
    AuthStatus,
    LoginIn,
    Me,
    PasswordIn,
    SetupIn,
    TokenCreate,
    TokenCreated,
    TokenRead,
    UserRead,
    WorkspaceMembership,
    WorkspaceSwitch,
)
from app.modules.auth.security import WeakPasswordError
from app.modules.auth.throttle import Throttle, get_throttle
from app.modules.users.models import User
from app.modules.workspaces import service as workspaces

public_router = APIRouter(prefix="/auth", tags=["auth"])
router = APIRouter(prefix="/auth", tags=["auth"])

ThrottleDep = Annotated[Throttle, Depends(get_throttle)]


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(service.SESSION_TTL.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=get_settings().environment != "development",
        path="/",
    )


def _bad(exc: Exception, code: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
    return HTTPException(code, str(exc))


async def me_payload(session: SessionDep, principal: service.Principal) -> Me:
    rows = await workspaces.user_workspaces(session, principal.user.id)
    if principal.token is not None:  # a token sees only its own workspace
        rows = [(w, r) for w, r in rows if w.id == principal.workspace_id]
    return Me(
        user=UserRead.model_validate(principal.user),
        workspaces=[WorkspaceMembership(id=w.id, name=w.name, role=r) for w, r in rows],
        active_workspace_id=principal.workspace_id,
        via="token" if principal.token else "session",
    )


async def sign_in(
    session: SessionDep,
    request: Request,
    response: Response,
    user: User,
    workspace_id: uuid.UUID | None = None,
) -> Me:
    token = await service.start_session(
        session, user, request.headers.get("user-agent", ""), workspace_id
    )
    set_session_cookie(response, token)
    principal = await service.resolve_session(session, token)
    assert principal is not None
    return await me_payload(session, principal)


# ---------- public ----------


@public_router.get("/status", response_model=AuthStatus)
async def auth_status(request: Request, session: SessionDep) -> AuthStatus:
    cookie = request.cookies.get(SESSION_COOKIE)
    signed_in = bool(cookie) and await service.resolve_session(session, cookie) is not None
    return AuthStatus(
        needs_setup=await service.needs_setup(session),
        signup_open=get_settings().allow_signup,
        signed_in=signed_in,
    )


@public_router.post("/setup", response_model=Me, status_code=status.HTTP_201_CREATED)
async def setup(data: SetupIn, request: Request, response: Response, session: SessionDep) -> Me:
    """First run only: create the instance owner, claiming the existing dev data."""
    check_origin(request)
    try:
        user = await service.setup(
            session, email=data.email, name=data.name, password=data.password
        )
    except WeakPasswordError as exc:
        raise _bad(exc, status.HTTP_422_UNPROCESSABLE_CONTENT) from exc
    except service.AuthError as exc:
        raise _bad(exc, status.HTTP_409_CONFLICT) from exc
    return await sign_in(session, request, response, user)


@public_router.post("/signup", response_model=Me, status_code=status.HTTP_201_CREATED)
async def signup(data: SetupIn, request: Request, response: Response, session: SessionDep) -> Me:
    """Open sign-up, only when ALLOW_SIGNUP is set. Otherwise people join through invitations."""
    check_origin(request)
    if not get_settings().allow_signup:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sign-up is by invitation only")
    try:
        user = await service.signup(
            session, email=data.email, name=data.name, password=data.password
        )
    except WeakPasswordError as exc:
        raise _bad(exc, status.HTTP_422_UNPROCESSABLE_CONTENT) from exc
    except service.AuthError as exc:
        raise _bad(exc, status.HTTP_409_CONFLICT) from exc
    return await sign_in(session, request, response, user)


@public_router.post("/login", response_model=Me)
async def login(
    data: LoginIn,
    request: Request,
    response: Response,
    session: SessionDep,
    throttle: ThrottleDep,
) -> Me:
    check_origin(request)
    try:
        user = await service.login(session, throttle, email=data.email, password=data.password)
    except service.ThrottledError as exc:
        raise _bad(exc, status.HTTP_429_TOO_MANY_REQUESTS) from exc
    except service.AuthError as exc:
        raise _bad(exc, status.HTTP_401_UNAUTHORIZED) from exc
    return await sign_in(session, request, response, user)


@public_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, session: SessionDep) -> None:
    """Ends this browser's session (if any) and clears the cookie."""
    check_origin(request)
    cookie = request.cookies.get(SESSION_COOKIE)
    if cookie:
        principal = await service.resolve_session(session, cookie)
        if principal and principal.session:
            await service.end_session(session, principal.session)
    response.delete_cookie(SESSION_COOKIE, path="/")


# ---------- signed in ----------


@router.get("/me", response_model=Me)
async def me(session: SessionDep, principal: CurrentPrincipal) -> Me:
    return await me_payload(session, principal)


@router.post("/workspace", response_model=Me)
async def switch_workspace(
    data: WorkspaceSwitch, session: SessionDep, principal: CurrentPrincipal
) -> Me:
    try:
        await service.switch_workspace(session, principal, data.workspace_id)
    except LookupError as exc:
        raise _bad(exc, status.HTTP_404_NOT_FOUND) from exc
    except service.AuthError as exc:
        raise _bad(exc, status.HTTP_409_CONFLICT) from exc
    principal.workspace_id = data.workspace_id
    return await me_payload(session, principal)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    data: PasswordIn, session: SessionDep, principal: CurrentPrincipal
) -> None:
    """Changes the password and signs out every other session."""
    if principal.session is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sign in with a password to change it")
    try:
        await service.change_password(session, principal, current=data.current, new=data.new)
    except WeakPasswordError as exc:
        raise _bad(exc, status.HTTP_422_UNPROCESSABLE_CONTENT) from exc
    except service.AuthError as exc:
        raise _bad(exc) from exc


@router.get("/tokens", response_model=list[TokenRead])
async def list_tokens(session: SessionDep, principal: CurrentPrincipal) -> list:
    return await service.list_tokens(session, principal.user.id)


@router.post("/tokens", response_model=TokenCreated, status_code=status.HTTP_201_CREATED)
async def create_token(data: TokenCreate, session: SessionDep, principal: CurrentPrincipal) -> dict:
    """The token is bound to the active workspace and shown only in this response."""
    if principal.session is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Create tokens from a signed-in browser")
    try:
        row, raw = await service.create_token(session, principal, data.name)
    except service.AuthError as exc:
        raise _bad(exc, status.HTTP_409_CONFLICT) from exc
    return {**TokenRead.model_validate(row).model_dump(), "token": raw}


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_token(
    token_id: uuid.UUID, session: SessionDep, principal: CurrentPrincipal
) -> None:
    try:
        await service.revoke_token(session, principal.user.id, token_id)
    except LookupError as exc:
        raise _bad(exc, status.HTTP_404_NOT_FOUND) from exc
