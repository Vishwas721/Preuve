import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.core.deps import CurrentUser, SessionDep
from app.modules.ideas import service
from app.modules.ideas.models import Idea


async def get_owned_idea(idea_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Idea:
    """Resolve `{idea_id}` from the path, 404 unless it belongs to the current user."""
    idea = await service.get_idea(session, user.id, idea_id)
    if idea is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Idea not found")
    return idea


OwnedIdea = Annotated[Idea, Depends(get_owned_idea)]
