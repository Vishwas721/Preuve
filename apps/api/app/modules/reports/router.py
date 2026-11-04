import logging
import re
import uuid

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.core.deps import CurrentPrincipal, SessionDep
from app.modules.ideas import service as ideas
from app.modules.ideas.deps import OwnedIdea, can_access
from app.modules.reports import service
from app.modules.reports.models import Report
from app.modules.reports.schemas import ReportRead
from app.workers.queue import QueueDep

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reports"])


async def _owned(session: SessionDep, principal: CurrentPrincipal, report_id: uuid.UUID) -> Report:
    row = await service.get_report(session, report_id)
    ws = await ideas.workspace_of(session, row.idea_id) if row else None
    if row is None or ws is None or not await can_access(session, principal, ws):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    return row


@router.get("/ideas/{idea_id}/reports", response_model=list[ReportRead])
async def list_reports(idea: OwnedIdea, session: SessionDep) -> list[dict]:
    return [await service.read(session, r) for r in await service.list_reports(session, idea.id)]


@router.post(
    "/ideas/{idea_id}/reports", response_model=ReportRead, status_code=status.HTTP_201_CREATED
)
async def create_report(idea: OwnedIdea, session: SessionDep, queue: QueueDep) -> dict:
    """Snapshot the score and queue the report (the summary runs on the worker)."""
    row = await service.create(session, idea)
    try:
        await queue.enqueue_job("validation_report", str(row.id))
    except Exception as exc:
        logger.exception("could not enqueue validation_report")
        await service.mark_failed(session, row.id, "Could not reach the job queue.")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Job queue unavailable, try again shortly"
        ) from exc
    return await service.read(session, row)


@router.get("/reports/{report_id}", response_model=ReportRead)
async def get_report(
    report_id: uuid.UUID, session: SessionDep, principal: CurrentPrincipal
) -> dict:
    return await service.read(session, await _owned(session, principal, report_id))


@router.get("/reports/{report_id}/markdown")
async def download_report(
    report_id: uuid.UUID, session: SessionDep, principal: CurrentPrincipal
) -> Response:
    row = await _owned(session, principal, report_id)
    if row.status != "done":
        raise HTTPException(status.HTTP_409_CONFLICT, "The report isn't ready yet")
    title = row.content.splitlines()[0].removeprefix("# Validation report: ") if row.content else ""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "idea"
    stamp = f"{row.generated_at:%Y-%m-%d}" if row.generated_at else "draft"
    return Response(
        row.content,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="preuve-{slug}-{stamp}.md"',
        },
    )


@router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: uuid.UUID, session: SessionDep, principal: CurrentPrincipal
) -> None:
    await service.delete(session, await _owned(session, principal, report_id))
