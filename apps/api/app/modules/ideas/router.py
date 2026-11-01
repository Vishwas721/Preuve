from fastapi import APIRouter, status

from app.core.deps import CurrentUser, SessionDep
from app.modules.ideas import service
from app.modules.ideas.deps import OwnedIdea
from app.modules.ideas.models import Idea
from app.modules.ideas.schemas import IdeaCreate, IdeaRead, IdeaUpdate

router = APIRouter(prefix="/ideas", tags=["ideas"])


@router.get("", response_model=list[IdeaRead])
async def list_ideas(session: SessionDep, user: CurrentUser) -> list[Idea]:
    return await service.list_ideas(session, user.id)


@router.post("", response_model=IdeaRead, status_code=status.HTTP_201_CREATED)
async def create_idea(data: IdeaCreate, session: SessionDep, user: CurrentUser) -> Idea:
    return await service.create_idea(session, user.id, data)


@router.get("/{idea_id}", response_model=IdeaRead)
async def get_idea(idea: OwnedIdea) -> Idea:
    return idea


@router.patch("/{idea_id}", response_model=IdeaRead)
async def update_idea(idea: OwnedIdea, data: IdeaUpdate, session: SessionDep) -> Idea:
    return await service.update_idea(session, idea, data)


@router.delete("/{idea_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_idea(idea: OwnedIdea, session: SessionDep) -> None:
    await service.delete_idea(session, idea)
