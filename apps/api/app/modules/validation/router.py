from fastapi import APIRouter, status

from app.core.deps import SessionDep
from app.modules.ideas.deps import OwnedIdea
from app.modules.validation import service
from app.modules.validation.models import ValidationScore
from app.modules.validation.schemas import ScoreRead, ScoreStatus, ScoreSummary

router = APIRouter(prefix="/ideas/{idea_id}", tags=["validation"])


@router.get("/score", response_model=ScoreStatus)
async def get_score(idea: OwnedIdea, session: SessionDep) -> dict:
    """The latest score snapshot, and `stale` when the stored evidence changed since."""
    row = await service.latest(session, idea.id)
    stale = row is None or row.inputs_hash != await service.current_hash(session, idea)
    return {"score": row, "stale": stale}


@router.post("/score", response_model=ScoreRead, status_code=status.HTTP_201_CREATED)
async def recompute_score(idea: OwnedIdea, session: SessionDep) -> ValidationScore:
    """Recompute from stored data (deterministic, no LLM) and update the idea's state."""
    return await service.recompute(session, idea)


@router.get("/score/history", response_model=list[ScoreSummary])
async def score_history(idea: OwnedIdea, session: SessionDep) -> list[ValidationScore]:
    return await service.history(session, idea.id)
