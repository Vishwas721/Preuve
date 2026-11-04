import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentPrincipal, SessionDep
from app.modules.auth.service import Principal
from app.modules.ideas import service
from app.modules.ideas.models import Idea
from app.modules.workspaces import service as workspaces


async def can_access(session: AsyncSession, principal: Principal, workspace_id: uuid.UUID) -> bool:
    """Members of the workspace only; an API token only in the workspace it's bound to."""
    if principal.token is not None and principal.token.workspace_id != workspace_id:
        return False
    return await workspaces.role_of(session, principal.user.id, workspace_id) is not None


async def get_owned_idea(
    idea_id: uuid.UUID, session: SessionDep, principal: CurrentPrincipal
) -> Idea:
    """Resolve `{idea_id}` from the path. 404 (not 403) for other workspaces, so ids can't be
    probed."""
    idea = await service.get_idea(session, idea_id)
    if idea is None or not await can_access(session, principal, idea.workspace_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Idea not found")
    return idea


OwnedIdea = Annotated[Idea, Depends(get_owned_idea)]
