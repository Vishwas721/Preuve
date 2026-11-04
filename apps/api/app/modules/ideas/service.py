import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ideas.models import Idea
from app.modules.ideas.schemas import IdeaCreate, IdeaUpdate


async def list_ideas(session: AsyncSession, workspace_id: uuid.UUID) -> list[Idea]:
    result = await session.scalars(
        select(Idea).where(Idea.workspace_id == workspace_id).order_by(Idea.created_at.desc())
    )
    return list(result)


async def get_idea(session: AsyncSession, idea_id: uuid.UUID) -> Idea | None:
    """No access check: callers authorise (see `ideas.deps.get_owned_idea`)."""
    return await session.get(Idea, idea_id)


async def workspace_of(session: AsyncSession, idea_id: uuid.UUID) -> uuid.UUID | None:
    return await session.scalar(select(Idea.workspace_id).where(Idea.id == idea_id))


async def create_idea(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    data: IdeaCreate,
    created_by_id: uuid.UUID | None = None,
) -> Idea:
    idea = Idea(workspace_id=workspace_id, created_by_id=created_by_id, **data.model_dump())
    session.add(idea)
    await session.commit()
    await session.refresh(idea)
    return idea


async def update_idea(session: AsyncSession, idea: Idea, data: IdeaUpdate) -> Idea:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(idea, field, value)
    await session.commit()
    await session.refresh(idea)
    return idea


async def delete_idea(session: AsyncSession, idea: Idea) -> None:
    await session.delete(idea)
    await session.commit()
