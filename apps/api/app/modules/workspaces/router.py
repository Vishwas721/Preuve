"""Workspaces, members and invitations (Phase 5A). Owners manage; members can view members."""

import uuid

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from app.core.deps import CurrentPrincipal, SessionDep, check_origin
from app.modules.auth import service as auth
from app.modules.auth.router import me_payload, sign_in
from app.modules.auth.schemas import InviteSignupIn, Me
from app.modules.auth.security import WeakPasswordError
from app.modules.auth.service import Principal
from app.modules.users.models import User
from app.modules.workspaces import service
from app.modules.workspaces.models import Role, Workspace
from app.modules.workspaces.schemas import (
    InvitationCreated,
    InvitationIn,
    InvitationPublic,
    InvitationRead,
    MemberRead,
    RoleIn,
    WorkspaceIn,
    WorkspaceRead,
)

router = APIRouter(tags=["workspaces"])
public_router = APIRouter(tags=["workspaces"])


async def _workspace(
    session: SessionDep, principal: Principal, workspace_id: uuid.UUID, *, owner: bool
) -> Workspace:
    """404 for non-members (and for API tokens of another workspace); 403 for members when an
    owner is needed. Managing a workspace needs a browser session, not an API token."""
    role = await service.role_of(session, principal.user.id, workspace_id)
    if role is None or (principal.token and principal.token.workspace_id != workspace_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    if owner and (role != Role.OWNER or principal.session is None):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a workspace owner can do this")
    ws = await service.get_workspace(session, workspace_id)
    assert ws is not None
    return ws


def _conflict(exc: Exception) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.post("/workspaces", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
async def create_workspace(data: WorkspaceIn, session: SessionDep, principal: CurrentPrincipal):
    if principal.session is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Create workspaces from a signed-in browser")
    ws = await service.create_workspace(session, data.name, principal.user)
    await session.commit()
    return ws


@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceRead)
async def rename_workspace(
    workspace_id: uuid.UUID, data: WorkspaceIn, session: SessionDep, principal: CurrentPrincipal
):
    ws = await _workspace(session, principal, workspace_id, owner=True)
    return await service.rename(session, ws, data.name)


@router.get("/workspaces/{workspace_id}/members", response_model=list[MemberRead])
async def list_members(workspace_id: uuid.UUID, session: SessionDep, principal: CurrentPrincipal):
    await _workspace(session, principal, workspace_id, owner=False)
    return [
        MemberRead(user_id=u.id, name=u.name, email=u.email, role=r, joined_at=at)
        for u, r, at in await service.members(session, workspace_id)
    ]


@router.patch(
    "/workspaces/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def set_role(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    data: RoleIn,
    session: SessionDep,
    principal: CurrentPrincipal,
) -> None:
    await _workspace(session, principal, workspace_id, owner=True)
    try:
        await service.set_role(session, workspace_id, user_id, data.role)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except service.WorkspaceError as exc:
        raise _conflict(exc) from exc


@router.delete(
    "/workspaces/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_member(
    workspace_id: uuid.UUID, user_id: uuid.UUID, session: SessionDep, principal: CurrentPrincipal
) -> None:
    """Owners remove anyone; a member can remove themselves (leave)."""
    leaving = user_id == principal.user.id
    await _workspace(session, principal, workspace_id, owner=not leaving)
    try:
        await service.remove_member(session, workspace_id, user_id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except service.WorkspaceError as exc:
        raise _conflict(exc) from exc


@router.get("/workspaces/{workspace_id}/invitations", response_model=list[InvitationRead])
async def list_invitations(
    workspace_id: uuid.UUID, session: SessionDep, principal: CurrentPrincipal
):
    await _workspace(session, principal, workspace_id, owner=True)
    return await service.list_invitations(session, workspace_id)


@router.post(
    "/workspaces/{workspace_id}/invitations",
    response_model=InvitationCreated,
    status_code=status.HTTP_201_CREATED,
)
async def invite(
    workspace_id: uuid.UUID, data: InvitationIn, session: SessionDep, principal: CurrentPrincipal
) -> dict:
    """Returns the invitation token once; share the link yourself (no email is sent)."""
    await _workspace(session, principal, workspace_id, owner=True)
    try:
        inv, token = await service.invite(
            session, workspace_id, data.email, data.role, principal.user
        )
    except service.WorkspaceError as exc:
        raise _conflict(exc) from exc
    return {**InvitationRead.model_validate(inv).model_dump(), "token": token}


@router.delete(
    "/workspaces/{workspace_id}/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_invitation(
    workspace_id: uuid.UUID,
    invitation_id: uuid.UUID,
    session: SessionDep,
    principal: CurrentPrincipal,
) -> None:
    await _workspace(session, principal, workspace_id, owner=True)
    try:
        await service.revoke_invitation(session, workspace_id, invitation_id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


# ---------- invitation links ----------


async def _usable(session: SessionDep, token: str):
    inv = await service.invitation_by_token(session, token)
    if inv is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "This invitation is invalid, used, revoked or expired"
        )
    return inv


@public_router.get("/invitations/{token}", response_model=InvitationPublic)
async def get_invitation(token: str, session: SessionDep) -> InvitationPublic:
    inv = await _usable(session, token)
    ws = await service.get_workspace(session, inv.workspace_id)
    exists = await session.scalar(select(User.id).where(User.email == inv.email)) is not None
    return InvitationPublic(
        workspace_name=ws.name if ws else "",
        email=inv.email,
        role=inv.role,
        expires_at=inv.expires_at,
        account_exists=exists,
    )


@router.post("/invitations/{token}/accept", response_model=Me)
async def accept_invitation(token: str, session: SessionDep, principal: CurrentPrincipal) -> Me:
    """Join as the signed-in user (who must have the invited email); switches to the workspace."""
    if principal.session is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Accept invitations from a browser")
    inv = await _usable(session, token)
    try:
        ws = await service.accept(session, inv, principal.user)
    except service.WorkspaceError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    await auth.switch_workspace(session, principal, ws.id)
    principal.workspace_id = ws.id
    return await me_payload(session, principal)


@public_router.post(
    "/invitations/{token}/signup", response_model=Me, status_code=status.HTTP_201_CREATED
)
async def signup_with_invitation(
    token: str, data: InviteSignupIn, request: Request, response: Response, session: SessionDep
) -> Me:
    """Create an account for the invited email (works even with open sign-up off)."""
    check_origin(request)
    inv = await _usable(session, token)
    try:
        user = await auth.signup_with_invite(session, inv, name=data.name, password=data.password)
    except WeakPasswordError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except auth.AuthError as exc:
        raise _conflict(exc) from exc
    # Land in the workspace they were invited to.
    return await sign_in(session, request, response, user, inv.workspace_id)
