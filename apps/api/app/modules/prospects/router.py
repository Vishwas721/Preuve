import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.deps import SessionDep
from app.modules.ideas.deps import OwnedIdea
from app.modules.prospects import service
from app.modules.prospects.models import ProspectStatus
from app.modules.prospects.schemas import ProspectDetail, ProspectSummary, ProspectUpdate

router = APIRouter(prefix="/ideas/{idea_id}", tags=["prospects"])


@router.get("/prospects", response_model=list[ProspectSummary])
async def list_prospects(
    idea: OwnedIdea,
    session: SessionDep,
    status_filter: ProspectStatus | None = None,
    min_score: int | None = None,
) -> list[dict]:
    """Companies for this idea, best score first."""
    return await service.list_prospects(session, idea.id, status=status_filter, min_score=min_score)


@router.post("/prospects/rescore")
async def rescore(idea: OwnedIdea, session: SessionDep) -> dict[str, int]:
    """Recompute every score from stored data (e.g. after changing the primary ICP)."""
    return {"rescored": await service.rescore_idea(session, idea.id)}


@router.get("/prospects/{company_id}", response_model=ProspectDetail)
async def get_prospect(idea: OwnedIdea, company_id: uuid.UUID, session: SessionDep) -> dict:
    company = await service.get_company(session, idea.id, company_id)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect not found")
    return await service.prospect_detail(session, company)


@router.patch("/prospects/{company_id}", response_model=ProspectDetail)
async def update_prospect(
    idea: OwnedIdea, company_id: uuid.UUID, data: ProspectUpdate, session: SessionDep
) -> dict:
    company = await service.get_company(session, idea.id, company_id)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect not found")
    try:
        await service.update_prospect(session, company, data)
    except service.ProspectError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return await service.prospect_detail(session, company)


@router.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(idea: OwnedIdea, contact_id: uuid.UUID, session: SessionDep) -> None:
    """Permanently delete a person's data (PRD §37)."""
    if not await service.delete_contact(session, idea.id, contact_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
