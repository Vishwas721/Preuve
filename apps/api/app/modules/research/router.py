import logging
import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.deps import SessionDep
from app.modules.ideas.deps import OwnedIdea
from app.modules.research import service
from app.modules.research.models import ResearchImport, Verification
from app.modules.research.pack import EvidenceKind, ResearchPack, Stance
from app.modules.research.schemas import (
    EvidenceRead,
    EvidenceUpdate,
    FindingRead,
    IdeaResearchRead,
    ResearchImportRead,
)
from app.workers.queue import QueueDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ideas/{idea_id}", tags=["research"])


@router.get("/research", response_model=IdeaResearchRead)
async def get_research(idea: OwnedIdea, session: SessionDep) -> IdeaResearchRead:
    return IdeaResearchRead(
        evidence=[EvidenceRead(**e) for e in await service.list_evidence(session, idea.id)],
        findings=[
            FindingRead.model_validate(f) for f in await service.latest_findings(session, idea.id)
        ],
        imports=[
            ResearchImportRead.model_validate(i)
            for i in await service.list_imports(session, idea.id)
        ],
    )


@router.post(
    "/research-imports", response_model=ResearchImportRead, status_code=status.HTTP_202_ACCEPTED
)
async def create_import(
    idea: OwnedIdea, pack: ResearchPack, session: SessionDep, queue: QueueDep
) -> ResearchImport:
    """Import a research pack; every quote is verified against its page in the background."""
    errors = await service.validate_for_idea(session, idea, pack)
    if errors:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, errors)
    imp = await service.create_import(session, idea, pack)
    try:
        await queue.enqueue_job("verify_research_import", str(imp.id))
    except Exception as exc:
        logger.exception("could not enqueue research import %s", imp.id)
        await service.fail_import(session, imp, "Could not reach the job queue (is Redis running?)")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Job queue unavailable, try again shortly"
        ) from exc
    return imp


@router.get("/research-imports", response_model=list[ResearchImportRead])
async def list_imports(idea: OwnedIdea, session: SessionDep) -> list[ResearchImport]:
    return await service.list_imports(session, idea.id)


@router.get("/research-imports/{import_id}", response_model=ResearchImportRead)
async def get_import(idea: OwnedIdea, import_id: uuid.UUID, session: SessionDep) -> ResearchImport:
    imp = await service.get_import(session, idea.id, import_id)
    if imp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Import not found")
    return imp


@router.get("/evidence", response_model=list[EvidenceRead])
async def list_evidence(
    idea: OwnedIdea,
    session: SessionDep,
    stance: Stance | None = None,
    kind: EvidenceKind | None = None,
    verification: Verification | None = None,
    unknown_id: uuid.UUID | None = None,
    include_dismissed: bool = False,
) -> list[EvidenceRead]:
    rows = await service.list_evidence(
        session,
        idea.id,
        include_dismissed=include_dismissed,
        unknown_id=unknown_id,
        filters={"stance": stance, "kind": kind, "verification": verification},
    )
    return [EvidenceRead(**r) for r in rows]


@router.patch("/evidence/{evidence_id}", response_model=EvidenceRead)
async def update_evidence(
    idea: OwnedIdea, evidence_id: uuid.UUID, data: EvidenceUpdate, session: SessionDep
) -> EvidenceRead:
    evidence = await service.get_evidence(session, idea.id, evidence_id)
    if evidence is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")
    await service.update_evidence(session, evidence, data)
    rows = await service.list_evidence(session, idea.id, include_dismissed=True)
    return EvidenceRead(**next(r for r in rows if r["id"] == evidence_id))
