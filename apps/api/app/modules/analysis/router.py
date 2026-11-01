import logging
import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.deps import SessionDep
from app.modules.analysis import service
from app.modules.analysis.models import ICP, AnalysisRun, Hypothesis, RunKind, Unknown
from app.modules.analysis.schemas import (
    AnalysisRunRead,
    HypothesisEdit,
    HypothesisRead,
    ICPCreate,
    ICPRead,
    ICPUpdate,
    IdeaAnalysisRead,
    UnknownCreate,
    UnknownRead,
    UnknownUpdate,
)
from app.modules.ideas.deps import OwnedIdea
from app.modules.ideas.models import Idea
from app.workers.queue import QueueDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ideas/{idea_id}", tags=["analysis"])


@router.get("/analysis", response_model=IdeaAnalysisRead)
async def get_analysis(idea: OwnedIdea, session: SessionDep) -> IdeaAnalysisRead:
    return IdeaAnalysisRead(
        hypothesis=await service.get_current_hypothesis(session, idea.id),
        unknowns=await service.list_unknowns(session, idea.id),
        icps=await service.list_icps(session, idea.id),
        latest_run=await service.latest_run(session, idea.id),
    )


# ---------- runs ----------


async def _start(session: SessionDep, queue: QueueDep, idea: Idea, kind: RunKind) -> AnalysisRun:
    try:
        run = await service.start_run(session, idea, kind)
    except service.ActiveRunError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except service.NoHypothesisError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    try:
        await queue.enqueue_job("run_analysis", str(run.id))
    except Exception as exc:
        logger.exception("could not enqueue analysis run %s", run.id)
        await service.fail_run(session, run, "Could not reach the job queue (is Redis running?)")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Job queue unavailable, try again shortly"
        ) from exc
    return run


@router.post("/analyze", response_model=AnalysisRunRead, status_code=status.HTTP_202_ACCEPTED)
async def analyze(idea: OwnedIdea, session: SessionDep, queue: QueueDep) -> AnalysisRun:
    """Generate hypothesis + unknowns + ICPs in the background."""
    return await _start(session, queue, idea, RunKind.FULL)


@router.post("/icps/generate", response_model=AnalysisRunRead, status_code=status.HTTP_202_ACCEPTED)
async def generate_icps(idea: OwnedIdea, session: SessionDep, queue: QueueDep) -> AnalysisRun:
    """Regenerate ICPs only, from the current hypothesis."""
    return await _start(session, queue, idea, RunKind.ICPS)


@router.get("/analysis-runs/{run_id}", response_model=AnalysisRunRead)
async def get_run(idea: OwnedIdea, run_id: uuid.UUID, session: SessionDep) -> AnalysisRun:
    run = await service.get_run(session, idea.id, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    return run


# ---------- hypothesis ----------


@router.get("/hypothesis/versions", response_model=list[HypothesisRead])
async def hypothesis_versions(idea: OwnedIdea, session: SessionDep) -> list[Hypothesis]:
    return await service.list_hypothesis_versions(session, idea.id)


@router.post("/hypothesis", response_model=HypothesisRead, status_code=status.HTTP_201_CREATED)
async def edit_hypothesis(idea: OwnedIdea, data: HypothesisEdit, session: SessionDep) -> Hypothesis:
    """Save an edit as a new hypothesis version."""
    return await service.save_hypothesis_edit(session, idea.id, data)


# ---------- unknowns ----------


@router.get("/unknowns", response_model=list[UnknownRead])
async def list_unknowns(
    idea: OwnedIdea, session: SessionDep, include_dropped: bool = False
) -> list[Unknown]:
    return await service.list_unknowns(session, idea.id, include_dropped)


@router.post("/unknowns", response_model=UnknownRead, status_code=status.HTTP_201_CREATED)
async def create_unknown(idea: OwnedIdea, data: UnknownCreate, session: SessionDep) -> Unknown:
    return await service.create_unknown(session, idea.id, data)


@router.patch("/unknowns/{unknown_id}", response_model=UnknownRead)
async def update_unknown(
    idea: OwnedIdea, unknown_id: uuid.UUID, data: UnknownUpdate, session: SessionDep
) -> Unknown:
    unknown = await service.get_unknown(session, idea.id, unknown_id)
    if unknown is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown not found")
    return await service.update_unknown(session, unknown, data)


# ---------- ICPs ----------


@router.get("/icps", response_model=list[ICPRead])
async def list_icps(
    idea: OwnedIdea, session: SessionDep, include_dismissed: bool = False
) -> list[ICP]:
    return await service.list_icps(session, idea.id, include_dismissed)


@router.post("/icps", response_model=ICPRead, status_code=status.HTTP_201_CREATED)
async def create_icp(idea: OwnedIdea, data: ICPCreate, session: SessionDep) -> ICP:
    return await service.create_icp(session, idea.id, data)


@router.patch("/icps/{icp_id}", response_model=ICPRead)
async def update_icp(
    idea: OwnedIdea, icp_id: uuid.UUID, data: ICPUpdate, session: SessionDep
) -> ICP:
    icp = await service.get_icp(session, idea.id, icp_id)
    if icp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ICP not found")
    return await service.update_icp(session, icp, data)
