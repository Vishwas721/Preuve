import logging
import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.deps import SessionDep
from app.modules.ideas.deps import OwnedIdea
from app.modules.interviews import service
from app.modules.interviews.models import Interview
from app.modules.interviews.schemas import (
    InterviewCreate,
    InterviewRead,
    InterviewSummary,
    InterviewUpdate,
    NoteCreate,
)
from app.workers.queue import QueueDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ideas/{idea_id}", tags=["interviews"])

_JOBS = {"guide": "interview_guide", "extraction": "analyze_interview"}


async def _owned(session: SessionDep, idea_id: uuid.UUID, interview_id: uuid.UUID) -> Interview:
    row = await service.get_interview(session, idea_id, interview_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    return row


@router.get("/interviews", response_model=list[InterviewSummary])
async def list_interviews(idea: OwnedIdea, session: SessionDep) -> list:
    return await service.list_interviews(session, idea.id)


@router.post("/interviews", response_model=InterviewRead, status_code=status.HTTP_201_CREATED)
async def create_interview(idea: OwnedIdea, data: InterviewCreate, session: SessionDep) -> dict:
    try:
        row = await service.create(session, idea, data)
    except service.InterviewError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return await service.detail(session, row)


@router.get("/interviews/{interview_id}", response_model=InterviewRead)
async def get_interview(idea: OwnedIdea, interview_id: uuid.UUID, session: SessionDep) -> dict:
    return await service.detail(session, await _owned(session, idea.id, interview_id))


@router.patch("/interviews/{interview_id}", response_model=InterviewRead)
async def update_interview(
    idea: OwnedIdea, interview_id: uuid.UUID, data: InterviewUpdate, session: SessionDep
) -> dict:
    row = await _owned(session, idea.id, interview_id)
    await service.update(session, row, data)
    return await service.detail(session, row)


@router.delete("/interviews/{interview_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_interview(idea: OwnedIdea, interview_id: uuid.UUID, session: SessionDep) -> None:
    """Delete an interview with its notes and the evidence derived from them."""
    await service.delete_interview(session, await _owned(session, idea.id, interview_id))


@router.post("/interviews/{interview_id}/notes", response_model=InterviewRead)
async def add_note(
    idea: OwnedIdea, interview_id: uuid.UUID, data: NoteCreate, session: SessionDep
) -> dict:
    row = await _owned(session, idea.id, interview_id)
    await service.add_note(session, row, data)
    return await service.detail(session, row)


@router.delete("/interviews/{interview_id}/notes/{note_id}", response_model=InterviewRead)
async def delete_note(
    idea: OwnedIdea, interview_id: uuid.UUID, note_id: uuid.UUID, session: SessionDep
) -> dict:
    row = await _owned(session, idea.id, interview_id)
    if not await service.delete_note(session, row, note_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    return await service.detail(session, row)


async def _start(
    session: SessionDep, queue: QueueDep, idea_id: uuid.UUID, interview_id: uuid.UUID, which: str
) -> dict:
    row = await _owned(session, idea_id, interview_id)
    try:
        await service.start_job(session, row, which)
    except service.InterviewError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    try:
        await queue.enqueue_job(_JOBS[which], str(row.id))
    except Exception as exc:
        logger.exception("could not enqueue %s", _JOBS[which])
        await service.mark_failed(session, row.id, which, "Could not reach the job queue.")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Job queue unavailable, try again shortly"
        ) from exc
    return await service.detail(session, row)


@router.post("/interviews/{interview_id}/guide", response_model=InterviewRead)
async def generate_guide(
    idea: OwnedIdea, interview_id: uuid.UUID, session: SessionDep, queue: QueueDep
) -> dict:
    """Write a guide from the idea's open unknowns (local model)."""
    return await _start(session, queue, idea.id, interview_id, "guide")


@router.post("/interviews/{interview_id}/extract", response_model=InterviewRead)
async def extract(
    idea: OwnedIdea, interview_id: uuid.UUID, session: SessionDep, queue: QueueDep
) -> dict:
    """Extract conversation fields from the notes (local model, private)."""
    return await _start(session, queue, idea.id, interview_id, "extraction")


@router.post(
    "/interviews/{interview_id}/unknowns/{unknown_id}/confirm", response_model=InterviewRead
)
async def confirm_unknown(
    idea: OwnedIdea, interview_id: uuid.UUID, unknown_id: uuid.UUID, session: SessionDep
) -> dict:
    """Accept an answered unknown proposed by the extraction: links its evidence, marks it."""
    row = await _owned(session, idea.id, interview_id)
    try:
        await service.confirm_unknown(session, row, unknown_id)
    except service.InterviewError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return await service.detail(session, row)
