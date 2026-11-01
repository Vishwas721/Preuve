"""arq job functions. Each takes the arq `ctx` dict first; register new ones in `settings.py`.

Jobs are thin: open a DB session, call a module service, return a small summary.
"""

import logging
import uuid
from typing import Any

import app.db.models  # noqa: F401  (register every ORM mapper in the worker process)
from app.db.session import SessionLocal
from app.llm.router import get_llm_router
from app.modules.analysis import service as analysis

logger = logging.getLogger(__name__)


async def ping(ctx: dict[str, Any], message: str = "pong") -> str:
    """Trivial job used to verify the queue end to end."""
    logger.info("ping job %s: %s", ctx.get("job_id"), message)
    return message


async def run_analysis(ctx: dict[str, Any], run_id: str) -> str:
    """Phase 1A: hypothesis + unknowns + ICPs for one analysis run."""
    async with SessionLocal() as session:
        status = await analysis.execute_run(session, get_llm_router(), uuid.UUID(run_id))
    return status.value
