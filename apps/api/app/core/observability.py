"""Logging and error reporting for production (Phase 5D).

- `LOG_FORMAT=json`: one JSON object per log line, each carrying the request id.
- Every HTTP request gets a request id (kept from a valid incoming `X-Request-ID`, else new),
  returned as `X-Request-ID` and logged once with method, path, status and duration. The
  **query string is never logged**: it can hold personal data (e.g. `/privacy/people?email=`).
- `SENTRY_DSN` (optional): errors go to Sentry without request bodies, cookies, headers, query
  strings or user data. Off by default, so nothing leaves the machine.
"""

import json
import logging
import re
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_VALID_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")
access_logger = logging.getLogger("preuve.access")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        rid = request_id.get()
        if rid:
            out["request_id"] = rid
        for key in ("method", "path", "status", "duration_ms", "component"):
            if hasattr(record, key):
                out[key] = getattr(record, key)
        if record.exc_info:
            out["error"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False, default=str)


def configure_logging(log_format: str = "text", level: str = "INFO") -> None:
    """In JSON mode, route every logger (ours, uvicorn's, arq's) to stdout as JSON lines. In
    text mode (development, tests) leave logging as uvicorn/pytest set it up."""
    if log_format != "json":
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "arq"):
        lg = logging.getLogger(name)
        lg.handlers[:] = []
        lg.propagate = True
    # uvicorn's access log prints full URLs (query strings included): ours replaces it.
    logging.getLogger("uvicorn.access").disabled = True


class RequestContextMiddleware:
    """Request id + one access-log line per request (path only, never the query string)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope.get("headers", [])).get(b"x-request-id", b"").decode("latin-1")
        rid = incoming if _VALID_ID.match(incoming) else uuid.uuid4().hex
        token = request_id.set(rid)
        started = time.perf_counter()
        status = 500

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message["headers"] = [
                    *[
                        (k, v)
                        for k, v in message.get("headers", [])
                        if k.lower() != b"x-request-id"
                    ],
                    (b"x-request-id", rid.encode()),
                ]
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            path = scope.get("path", "")
            if path != "/health":  # health checks every few seconds would drown the log
                access_logger.info(
                    "%s %s %s",
                    scope.get("method"),
                    path,
                    status,
                    extra={
                        "method": scope.get("method"),
                        "path": path,
                        "status": status,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    },
                )
            request_id.reset(token)


def _scrub(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any]:
    """Keep only what's needed to debug: drop request data and user info."""
    req = event.get("request")
    if isinstance(req, dict):
        event["request"] = {
            "method": req.get("method"),
            "url": (req.get("url") or "").split("?")[0],
        }
    event.pop("user", None)
    rid = request_id.get()
    if rid:
        event.setdefault("tags", {})["request_id"] = rid
    return event


def init_sentry(dsn: str, environment: str, component: str) -> bool:
    """Start Sentry only when a DSN is configured. Returns whether it was started."""
    if not dsn:
        return False
    import sentry_sdk

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        send_default_pii=False,
        traces_sample_rate=0.0,
        max_request_body_size="never",
        before_send=_scrub,
    )
    sentry_sdk.set_tag("component", component)
    return True
