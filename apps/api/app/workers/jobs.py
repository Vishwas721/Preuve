"""arq job functions. Each takes the arq `ctx` dict first; register new ones in `settings.py`.

Jobs are thin: open a DB session, call a module service, return a small summary.
"""

import logging
import uuid
from typing import Any

import app.db.models  # noqa: F401  (register every ORM mapper in the worker process)
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.email import get_email_provider
from app.llm.router import get_llm_router
from app.modules.analysis import service as analysis
from app.modules.outreach import service as outreach
from app.modules.research import service as research
from app.search.fetch import PageFetcher

logger = logging.getLogger(__name__)


async def ping(ctx: dict[str, Any], message: str = "pong") -> str:
    """Trivial job used to verify the queue end to end."""
    logger.info("ping job %s: %s", ctx.get("job_id"), message)
    return message


async def run_analysis(ctx: dict[str, Any], run_id: str) -> str:
    """Phase 1A: hypothesis + unknowns + ICPs for one analysis run."""
    rid = uuid.UUID(run_id)
    try:
        async with SessionLocal() as session:
            status = await analysis.execute_run(session, get_llm_router(), rid)
    except Exception as exc:
        # Never leave a run stuck in queued/running: that would block the idea until it goes stale.
        logger.exception("analysis job crashed for run %s", run_id)
        async with SessionLocal() as session:
            await analysis.fail_if_active(session, rid, f"Worker error: {exc}")
        raise
    return status.value


async def verify_research_import(ctx: dict[str, Any], import_id: str) -> str:
    """Phase 1B: fetch every cited page and verify each quote in a research pack."""
    iid = uuid.UUID(import_id)
    try:
        async with SessionLocal() as session:
            status = await research.verify_import(session, PageFetcher(), iid)
    except Exception as exc:
        logger.exception("research import job crashed for %s", import_id)
        async with SessionLocal() as session:
            await research.fail_if_active(session, iid, f"Worker error: {exc}")
        raise
    return status.value


async def draft_outreach(ctx: dict[str, Any], message_ids: list[str]) -> dict[str, int]:
    """Phase 2: fill `drafting` messages with an LLM draft (citations verified)."""
    ids = [uuid.UUID(m) for m in message_ids]
    done: dict[str, int] = {}
    try:
        for mid in ids:
            async with SessionLocal() as session:
                result = await outreach.generate_draft(
                    session, get_llm_router(), mid, get_settings()
                )
            key = result.value if result else "skipped"
            done[key] = done.get(key, 0) + 1
    except Exception as exc:
        logger.exception("draft job crashed")
        async with SessionLocal() as session:
            await outreach.mark_draft_failed(session, ids, f"Worker error: {exc}")
        raise
    return done


async def send_campaign(
    ctx: dict[str, Any], campaign_id: str, message_ids: list[str] | None = None
) -> dict[str, Any]:
    """Phase 2: send approved messages; every safety rule is re-checked before each send."""
    async with SessionLocal() as session:
        return await outreach.send_campaign(
            session,
            get_email_provider(),
            uuid.UUID(campaign_id),
            get_settings(),
            [uuid.UUID(m) for m in message_ids] if message_ids else None,
        )
