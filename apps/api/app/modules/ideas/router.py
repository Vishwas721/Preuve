import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentUser, SessionDep
from app.modules.ideas import service
from app.modules.ideas.models import Idea
from app.modules.ideas.schemas import IdeaCreate, IdeaRead, IdeaUpdate

router = APIRouter(prefix="/ideas", tags=["ideas"])


async def _get_owned_idea(session: SessionDep, user: CurrentUser, idea_id: uuid.UUID) -> Idea:
    idea = await service.get_idea(session, user.id, idea_id)
    if idea is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Idea not found")
    return idea


@router.get("", response_model=list[IdeaRead])
async def list_ideas(session: SessionDep, user: CurrentUser) -> list[Idea]:
    return await service.list_ideas(session, user.id)


@router.post("", response_model=IdeaRead, status_code=status.HTTP_201_CREATED)
async def create_idea(data: IdeaCreate, session: SessionDep, user: CurrentUser) -> Idea:
    return await service.create_idea(session, user.id, data)


@router.get("/{idea_id}", response_model=IdeaRead)
async def get_idea(idea_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Idea:
    return await _get_owned_idea(session, user, idea_id)


@router.patch("/{idea_id}", response_model=IdeaRead)
async def update_idea(
    idea_id: uuid.UUID, data: IdeaUpdate, session: SessionDep, user: CurrentUser
) -> Idea:
    idea = await _get_owned_idea(session, user, idea_id)
    return await service.update_idea(session, idea, data)


@router.delete("/{idea_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_idea(idea_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> None:
    idea = await _get_owned_idea(session, user, idea_id)
    await service.delete_idea(session, idea)
