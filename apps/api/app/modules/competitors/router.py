import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.deps import SessionDep
from app.modules.competitors import service
from app.modules.competitors.schemas import CompetitorCreate, CompetitorRead, CompetitorUpdate
from app.modules.ideas.deps import OwnedIdea

router = APIRouter(prefix="/ideas/{idea_id}/competitors", tags=["competitors"])


async def _read(
    session: SessionDep, idea_id: uuid.UUID, competitor_id: uuid.UUID
) -> CompetitorRead:
    rows = await service.list_competitors(session, idea_id, include_dismissed=True)
    return CompetitorRead(**next(r for r in rows if r["id"] == competitor_id))


@router.get("", response_model=list[CompetitorRead])
async def list_competitors(
    idea: OwnedIdea, session: SessionDep, include_dismissed: bool = False
) -> list[CompetitorRead]:
    rows = await service.list_competitors(session, idea.id, include_dismissed)
    return [CompetitorRead(**r) for r in rows]


@router.post("", response_model=CompetitorRead, status_code=status.HTTP_201_CREATED)
async def create_competitor(
    idea: OwnedIdea, data: CompetitorCreate, session: SessionDep
) -> CompetitorRead:
    try:
        comp = await service.create_competitor(session, idea.id, data)
    except service.DuplicateCompetitorError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return await _read(session, idea.id, comp.id)


@router.patch("/{competitor_id}", response_model=CompetitorRead)
async def update_competitor(
    idea: OwnedIdea, competitor_id: uuid.UUID, data: CompetitorUpdate, session: SessionDep
) -> CompetitorRead:
    comp = await service.get_competitor(session, idea.id, competitor_id)
    if comp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Competitor not found")
    try:
        await service.update_competitor(session, comp, data)
    except service.DuplicateCompetitorError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return await _read(session, idea.id, competitor_id)
