import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.config import get_settings
from app.core.deps import SessionDep
from app.modules.ideas.deps import OwnedIdea
from app.modules.responses import service
from app.modules.responses.mailbox import get_mailbox
from app.modules.responses.models import Response
from app.modules.responses.schemas import (
    Dashboard,
    InboxStatus,
    ResponsePaste,
    ResponseRead,
    ResponseSummary,
)
from app.workers.queue import QueueDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ideas/{idea_id}", tags=["responses"])
inbox_router = APIRouter(tags=["responses"])

LAST_POLL_KEY = "preuve:inbox:last_poll"
_UNAVAILABLE = "Job queue unavailable, try again shortly"


async def _owned(session: SessionDep, idea_id: uuid.UUID, response_id: uuid.UUID) -> Response:
    response = await service.get_response(session, idea_id, response_id)
    if response is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reply not found")
    return response


async def _enqueue(session: SessionDep, queue: QueueDep, response_id: uuid.UUID) -> None:
    try:
        await queue.enqueue_job("analyze_response", str(response_id))
    except Exception as exc:
        logger.exception("could not enqueue analyze_response")
        await service.mark_failed(
            session, response_id, "Could not reach the job queue (is Redis running?). Reanalyze."
        )
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _UNAVAILABLE) from exc


@router.get("/responses", response_model=list[ResponseSummary])
async def list_responses(idea: OwnedIdea, session: SessionDep) -> list:
    return await service.list_responses(session, idea.id)


@router.get("/responses/dashboard", response_model=Dashboard)
async def dashboard(idea: OwnedIdea, session: SessionDep) -> dict:
    return await service.dashboard(session, idea.id)


@router.post("/responses", response_model=ResponseRead, status_code=status.HTTP_201_CREATED)
async def paste(idea: OwnedIdea, data: ResponsePaste, session: SessionDep, queue: QueueDep) -> dict:
    """Paste a reply; it's classified in the background on the local model."""
    try:
        response = await service.create_paste(session, idea, data)
    except service.ResponseError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    await _enqueue(session, queue, response.id)
    return await service.response_detail(session, response)


@router.get("/responses/{response_id}", response_model=ResponseRead)
async def get_response(idea: OwnedIdea, response_id: uuid.UUID, session: SessionDep) -> dict:
    return await service.response_detail(session, await _owned(session, idea.id, response_id))


@router.post("/responses/{response_id}/reanalyze", response_model=ResponseRead)
async def reanalyze(
    idea: OwnedIdea, response_id: uuid.UUID, session: SessionDep, queue: QueueDep
) -> dict:
    response = await _owned(session, idea.id, response_id)
    try:
        await service.reanalyze(session, response)
    except service.ResponseError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await _enqueue(session, queue, response.id)
    return await service.response_detail(session, response)


@router.delete("/responses/{response_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_response(idea: OwnedIdea, response_id: uuid.UUID, session: SessionDep) -> None:
    """Delete a reply and the evidence derived from it."""
    await service.delete_response(session, await _owned(session, idea.id, response_id))


# ---------- mailbox ----------


@inbox_router.get("/outreach/inbox", response_model=InboxStatus)
async def inbox_status(queue: QueueDep) -> InboxStatus:
    mailbox = get_mailbox(get_settings())
    last = None
    try:
        raw = await queue.get(LAST_POLL_KEY)  # type: ignore[attr-defined]
        last = json.loads(raw) if raw else None
    except Exception:  # Redis down or a fake queue: the status is optional
        last = None
    return InboxStatus(
        enabled=mailbox.enabled, mailbox=mailbox.label if mailbox.enabled else "", last_poll=last
    )


@inbox_router.post("/outreach/inbox/check", status_code=status.HTTP_202_ACCEPTED)
async def check_inbox(queue: QueueDep) -> dict[str, bool]:
    if not get_mailbox(get_settings()).enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "Mailbox polling is disabled (IMAP_HOST)")
    try:
        await queue.enqueue_job("imap_poll")
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _UNAVAILABLE) from exc
    return {"queued": True}
