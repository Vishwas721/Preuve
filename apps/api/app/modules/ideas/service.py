import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ideas.models import Idea
from app.modules.ideas.schemas import IdeaCreate, IdeaUpdate


async def list_ideas(session: AsyncSession, owner_id: uuid.UUID) -> list[Idea]:
    result = await session.scalars(
        select(Idea).where(Idea.owner_id == owner_id).order_by(Idea.created_at.desc())
    )
    return list(result)


async def get_idea(session: AsyncSession, owner_id: uuid.UUID, idea_id: uuid.UUID) -> Idea | None:
    return await session.scalar(select(Idea).where(Idea.id == idea_id, Idea.owner_id == owner_id))


async def create_idea(session: AsyncSession, owner_id: uuid.UUID, data: IdeaCreate) -> Idea:
    idea = Idea(owner_id=owner_id, **data.model_dump())
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
