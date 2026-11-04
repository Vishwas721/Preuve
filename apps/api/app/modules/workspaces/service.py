"""Workspaces, memberships and invitations (Phase 5A)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.security import INVITE_PREFIX, hash_token, new_token, normalize_email
from app.modules.users.models import User
from app.modules.workspaces.models import Invitation, Membership, Role, Workspace

INVITE_TTL = timedelta(days=7)


class WorkspaceError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


# ---------- workspaces ----------


async def create_workspace(session: AsyncSession, name: str, owner: User) -> Workspace:
    ws = Workspace(name=name.strip(), created_by_id=owner.id)
    session.add(ws)
    await session.flush()
    session.add(Membership(workspace_id=ws.id, user_id=owner.id, role=Role.OWNER))
    await session.flush()
    return ws


async def ensure_personal_workspace(session: AsyncSession, user: User) -> Workspace:
    """The user's first workspace; created with the account if they have none."""
    rows = await user_workspaces(session, user.id)
    if rows:
        return rows[0][0]
    return await create_workspace(session, f"{user.name}'s workspace", user)


async def personal_workspace_id(session: AsyncSession, user: User) -> uuid.UUID:
    ws = await ensure_personal_workspace(session, user)
    await session.commit()
    return ws.id


async def get_workspace(session: AsyncSession, workspace_id: uuid.UUID) -> Workspace | None:
    return await session.get(Workspace, workspace_id)


async def rename(session: AsyncSession, ws: Workspace, name: str) -> Workspace:
    ws.name = name.strip()
    await session.commit()
    return ws


# ---------- memberships ----------


async def user_workspaces(
    session: AsyncSession, user_id: uuid.UUID
) -> list[tuple[Workspace, Role]]:
    rows = await session.execute(
        select(Workspace, Membership.role)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .where(Membership.user_id == user_id)
        .order_by(Membership.created_at, Workspace.name)
    )
    return [(w, r) for w, r in rows]


async def role_of(
    session: AsyncSession, user_id: uuid.UUID, workspace_id: uuid.UUID
) -> Role | None:
    return await session.scalar(
        select(Membership.role).where(
            Membership.user_id == user_id, Membership.workspace_id == workspace_id
        )
    )


async def members(
    session: AsyncSession, workspace_id: uuid.UUID
) -> list[tuple[User, Role, datetime]]:
    rows = await session.execute(
        select(User, Membership.role, Membership.created_at)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.workspace_id == workspace_id)
        .order_by(Membership.created_at)
    )
    return [(u, r, at) for u, r, at in rows]


async def _owners(session: AsyncSession, workspace_id: uuid.UUID) -> int:
    return (
        await session.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.workspace_id == workspace_id, Membership.role == Role.OWNER)
        )
        or 0
    )


async def _membership(
    session: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> Membership:
    m = await session.scalar(
        select(Membership).where(
            Membership.workspace_id == workspace_id, Membership.user_id == user_id
        )
    )
    if m is None:
        raise LookupError("Not a member of this workspace")
    return m


async def set_role(
    session: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID, role: Role
) -> None:
    m = await _membership(session, workspace_id, user_id)
    if m.role == Role.OWNER and role != Role.OWNER and await _owners(session, workspace_id) <= 1:
        raise WorkspaceError("A workspace needs at least one owner.")
    m.role = role
    await session.commit()


async def remove_member(session: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Access ends at once: idea access is checked against memberships on every request."""
    m = await _membership(session, workspace_id, user_id)
    if m.role == Role.OWNER and await _owners(session, workspace_id) <= 1:
        raise WorkspaceError("A workspace needs at least one owner.")
    await session.delete(m)
    await session.commit()


async def add_member(
    session: AsyncSession, workspace_id: uuid.UUID, user: User, role: Role
) -> None:
    if await role_of(session, user.id, workspace_id) is None:
        session.add(Membership(workspace_id=workspace_id, user_id=user.id, role=role))
        await session.flush()


# ---------- invitations ----------


async def invite(
    session: AsyncSession, workspace_id: uuid.UUID, email: str, role: Role, by: User
) -> tuple[Invitation, str]:
    """Returns the invitation and its one-time token (only its hash is stored)."""
    email = normalize_email(email)
    existing = await session.scalar(
        select(User.id)
        .join(Membership, Membership.user_id == User.id)
        .where(User.email == email, Membership.workspace_id == workspace_id)
    )
    if existing is not None:
        raise WorkspaceError("That person is already a member.")
    token = new_token(INVITE_PREFIX)
    inv = Invitation(
        workspace_id=workspace_id,
        email=email,
        role=role,
        token_hash=hash_token(token),
        invited_by_id=by.id,
        expires_at=_now() + INVITE_TTL,
    )
    session.add(inv)
    await session.commit()
    await session.refresh(inv)
    return inv, token


async def list_invitations(session: AsyncSession, workspace_id: uuid.UUID) -> list[Invitation]:
    """Pending invitations (not accepted, revoked or expired)."""
    return list(
        await session.scalars(
            select(Invitation)
            .where(
                Invitation.workspace_id == workspace_id,
                Invitation.accepted_at.is_(None),
                Invitation.revoked_at.is_(None),
                Invitation.expires_at > _now(),
            )
            .order_by(Invitation.created_at.desc())
        )
    )


async def revoke_invitation(
    session: AsyncSession, workspace_id: uuid.UUID, invitation_id: uuid.UUID
) -> None:
    inv = await session.get(Invitation, invitation_id)
    if inv is None or inv.workspace_id != workspace_id:
        raise LookupError("Invitation not found")
    inv.revoked_at = _now()
    await session.commit()


async def invitation_by_token(session: AsyncSession, token: str) -> Invitation | None:
    """A usable invitation for this token, or None (unknown, used, revoked or expired)."""
    inv = await session.scalar(select(Invitation).where(Invitation.token_hash == hash_token(token)))
    if inv is None or inv.accepted_at or inv.revoked_at or inv.expires_at <= _now():
        return None
    return inv


async def accept(session: AsyncSession, inv: Invitation, user: User) -> Workspace:
    if normalize_email(user.email) != inv.email:
        raise WorkspaceError("This invitation is for a different email address.")
    await add_member(session, inv.workspace_id, user, inv.role)
    inv.accepted_at = _now()
    await session.commit()
    ws = await session.get(Workspace, inv.workspace_id)
    assert ws is not None
    return ws
