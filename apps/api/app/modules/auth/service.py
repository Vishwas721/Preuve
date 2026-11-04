"""Accounts, sessions and API tokens (Phase 5A).

Session and API tokens are random, returned once, and stored only as SHA-256 hashes.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.auth import security
from app.modules.auth.models import ApiToken, AuthSession
from app.modules.auth.throttle import Throttle
from app.modules.users.models import User
from app.modules.workspaces import service as workspaces
from app.modules.workspaces.models import Invitation

SESSION_TTL = timedelta(days=30)
SESSION_RENEW_AFTER = timedelta(hours=1)
GENERIC_LOGIN_ERROR = "Wrong email or password."


class AuthError(Exception):
    """Shown to the user as is."""


class ThrottledError(AuthError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Principal:
    """Who is calling and in which workspace. Exactly one of session / token is set."""

    user: User
    workspace_id: uuid.UUID | None
    session: AuthSession | None = None
    token: ApiToken | None = None


# ---------- setup and accounts ----------


async def needs_setup(session: AsyncSession) -> bool:
    """True until some user has a password (a fresh install, or the pre-5A dev data)."""
    return (
        await session.scalar(select(User.id).where(User.password_hash.is_not(None)).limit(1))
        is None
    )


async def setup(session: AsyncSession, *, email: str, name: str, password: str) -> User:
    """Create the instance owner. The pre-5A dev user, who owns any existing data, is claimed."""
    if not await needs_setup(session):
        raise AuthError("This Preuve is already set up. Sign in instead.")
    email = security.normalize_email(email)
    security.check_password_strength(password, email)
    dev_email = security.normalize_email(get_settings().dev_user_email)
    user = await session.scalar(select(User).where(User.email == dev_email))
    if user is None:
        user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, name=name.strip())
        session.add(user)
    elif user.email != email and await session.scalar(select(User.id).where(User.email == email)):
        raise AuthError("Another account already uses that email.")
    user.email, user.name = email, name.strip()
    user.password_hash = security.hash_password(password)
    await session.flush()
    await workspaces.ensure_personal_workspace(session, user)
    await session.commit()
    return user


async def signup(session: AsyncSession, *, email: str, name: str, password: str) -> User:
    """Open sign-up (only when ALLOW_SIGNUP is set): a new account with its own workspace."""
    email = security.normalize_email(email)
    if await session.scalar(select(User.id).where(User.email == email)):
        raise AuthError("An account with this email already exists. Sign in instead.")
    security.check_password_strength(password, email)
    user = User(email=email, name=name.strip(), password_hash=security.hash_password(password))
    session.add(user)
    await session.flush()
    await workspaces.ensure_personal_workspace(session, user)
    await session.commit()
    return user


async def signup_with_invite(
    session: AsyncSession, inv: Invitation, *, name: str, password: str
) -> User:
    if await session.scalar(select(User.id).where(User.email == inv.email)):
        raise AuthError("An account with this email exists. Sign in to accept the invitation.")
    security.check_password_strength(password, inv.email)
    user = User(email=inv.email, name=name.strip(), password_hash=security.hash_password(password))
    session.add(user)
    await session.flush()
    await workspaces.ensure_personal_workspace(session, user)
    await workspaces.accept(session, inv, user)
    return user


async def login(session: AsyncSession, throttle: Throttle, *, email: str, password: str) -> User:
    email = security.normalize_email(email)
    if await throttle.blocked(email):
        raise ThrottledError("Too many failed attempts. Try again in 15 minutes.")
    user = await session.scalar(select(User).where(User.email == email))
    ok = security.verify_password(user.password_hash if user else None, password)
    if not ok or user is None or not user.is_active:
        await throttle.fail(email)
        raise AuthError(GENERIC_LOGIN_ERROR)
    await throttle.reset(email)
    if security.needs_rehash(user.password_hash):
        user.password_hash = security.hash_password(password)
    user.last_login_at = _now()
    await session.commit()
    return user


async def change_password(
    session: AsyncSession, principal: Principal, *, current: str, new: str
) -> None:
    user = principal.user
    if not security.verify_password(user.password_hash, current):
        raise AuthError("Your current password is wrong.")
    security.check_password_strength(new, user.email)
    user.password_hash = security.hash_password(new)
    keep = principal.session.id if principal.session else None
    await session.execute(
        delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.id != keep)
    )
    await session.commit()


async def set_password(session: AsyncSession, email: str, password: str) -> User:
    """Admin reset from the CLI: sets the password and ends every session of that user."""
    user = await session.scalar(select(User).where(User.email == security.normalize_email(email)))
    if user is None:
        raise AuthError("No user with that email.")
    security.check_password_strength(password, user.email)
    user.password_hash = security.hash_password(password)
    await session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    await session.commit()
    return user


# ---------- sessions ----------


async def start_session(
    session: AsyncSession,
    user: User,
    user_agent: str = "",
    workspace_id: uuid.UUID | None = None,
) -> str:
    """A new session in `workspace_id` (if the user is a member) or their first workspace."""
    ws = await workspaces.ensure_personal_workspace(session, user)
    active = (
        workspace_id
        if workspace_id and await workspaces.role_of(session, user.id, workspace_id)
        else ws.id
    )
    token = security.new_token(security.SESSION_PREFIX)
    now = _now()
    session.add(
        AuthSession(
            user_id=user.id,
            token_hash=security.hash_token(token),
            active_workspace_id=active,
            expires_at=now + SESSION_TTL,
            last_seen_at=now,
            user_agent=user_agent[:300],
        )
    )
    await session.commit()
    return token


async def _active_workspace(
    session: AsyncSession, user: User, wanted: uuid.UUID | None
) -> uuid.UUID | None:
    """The wanted workspace if the user is still a member, else their first one."""
    if wanted and await workspaces.role_of(session, user.id, wanted):
        return wanted
    rows = await workspaces.user_workspaces(session, user.id)
    return rows[0][0].id if rows else None


async def resolve_session(session: AsyncSession, token: str) -> Principal | None:
    row = await session.scalar(
        select(AuthSession).where(AuthSession.token_hash == security.hash_token(token))
    )
    now = _now()
    if row is None or row.expires_at <= now:
        return None
    user = await session.get(User, row.user_id)
    if user is None or not user.is_active:
        return None
    ws = await _active_workspace(session, user, row.active_workspace_id)
    if ws != row.active_workspace_id or now - row.last_seen_at > SESSION_RENEW_AFTER:
        row.active_workspace_id = ws
        row.last_seen_at = now
        row.expires_at = now + SESSION_TTL  # sliding expiry
        await session.commit()
    return Principal(user=user, workspace_id=ws, session=row)


async def end_session(session: AsyncSession, row: AuthSession) -> None:
    await session.delete(row)
    await session.commit()


async def switch_workspace(
    session: AsyncSession, principal: Principal, workspace_id: uuid.UUID
) -> None:
    if principal.session is None:
        raise AuthError("API tokens are bound to one workspace.")
    if await workspaces.role_of(session, principal.user.id, workspace_id) is None:
        raise LookupError("Workspace not found")
    principal.session.active_workspace_id = workspace_id
    await session.commit()


# ---------- API tokens ----------


async def create_token(
    session: AsyncSession, principal: Principal, name: str
) -> tuple[ApiToken, str]:
    if principal.workspace_id is None:
        raise AuthError("No workspace to bind the token to.")
    raw = security.new_token(security.API_TOKEN_PREFIX)
    row = ApiToken(
        user_id=principal.user.id,
        workspace_id=principal.workspace_id,
        name=name.strip(),
        token_prefix=raw[:12],
        token_hash=security.hash_token(raw),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row, raw


async def list_tokens(session: AsyncSession, user_id: uuid.UUID) -> list[ApiToken]:
    return list(
        await session.scalars(
            select(ApiToken)
            .where(ApiToken.user_id == user_id, ApiToken.revoked_at.is_(None))
            .order_by(ApiToken.created_at.desc())
        )
    )


async def revoke_token(session: AsyncSession, user_id: uuid.UUID, token_id: uuid.UUID) -> None:
    row = await session.get(ApiToken, token_id)
    if row is None or row.user_id != user_id or row.revoked_at:
        raise LookupError("Token not found")
    row.revoked_at = _now()
    await session.commit()


async def resolve_token(session: AsyncSession, raw: str) -> Principal | None:
    row = await session.scalar(
        select(ApiToken).where(ApiToken.token_hash == security.hash_token(raw))
    )
    if row is None or row.revoked_at:
        return None
    user = await session.get(User, row.user_id)
    if user is None or not user.is_active:
        return None
    # A token stops working in a workspace its owner has left.
    if await workspaces.role_of(session, user.id, row.workspace_id) is None:
        return None
    now = _now()
    if row.last_used_at is None or now - row.last_used_at > SESSION_RENEW_AFTER:
        row.last_used_at = now
        await session.commit()
    return Principal(user=user, workspace_id=row.workspace_id, token=row)
