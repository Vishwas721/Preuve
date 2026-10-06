"""arq job functions. Each takes the arq `ctx` dict first.

Feature phases add their jobs here (or in their module) and register them in `settings.py`.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def ping(ctx: dict[str, Any], message: str = "pong") -> str:
    """Trivial job used to verify the queue end to end."""
    logger.info("ping job %s: %s", ctx.get("job_id"), message)
    return message
