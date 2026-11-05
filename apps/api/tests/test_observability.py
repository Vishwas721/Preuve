"""Phase 5D: JSON logs with request ids (never query strings) and an opt-in Sentry hook."""

import json
import logging

from httpx import AsyncClient

from app.core import observability
from app.core.observability import JsonFormatter, _scrub, init_sentry, request_id


async def test_every_response_has_a_request_id(client: AsyncClient) -> None:
    r = await client.get("/auth/me")
    assert len(r.headers["x-request-id"]) == 32
    kept = await client.get("/auth/me", headers={"X-Request-ID": "trace-1234abcd"})
    assert kept.headers["x-request-id"] == "trace-1234abcd"
    bad = await client.get("/auth/me", headers={"X-Request-ID": "x\r\ninjected"})
    assert bad.headers["x-request-id"] != "x\r\ninjected"


async def test_access_log_has_path_but_never_the_query_string(client: AsyncClient, caplog) -> None:
    caplog.set_level(logging.INFO, logger="preuve.access")
    await client.get("/privacy/people", params={"email": "jane.secret@abc.test"})
    lines = [r for r in caplog.records if r.name == "preuve.access"]
    assert lines and lines[-1].path == "/privacy/people" and lines[-1].status == 200
    assert all("jane.secret" not in r.getMessage() for r in caplog.records)
    assert all("jane.secret" not in str(getattr(r, "path", "")) for r in lines)


def test_json_formatter_emits_one_object_with_the_request_id() -> None:
    token = request_id.set("abc123def456")
    try:
        rec = logging.LogRecord("preuve.access", logging.INFO, __file__, 1, "GET %s", ("/x",), None)
        rec.status = 200
        out = json.loads(JsonFormatter().format(rec))
    finally:
        request_id.reset(token)
    assert out["message"] == "GET /x" and out["request_id"] == "abc123def456"
    assert out["status"] == 200 and out["level"] == "info" and out["time"].endswith("+00:00")


def test_sentry_is_off_without_a_dsn(monkeypatch) -> None:
    called = []
    monkeypatch.setattr("sentry_sdk.init", lambda **kw: called.append(kw))
    assert init_sentry("", "production", "api") is False and called == []
    assert init_sentry("https://k@o1.ingest.sentry.io/1", "production", "api") is True
    assert called[0]["send_default_pii"] is False
    assert called[0]["max_request_body_size"] == "never"


def test_sentry_events_are_scrubbed() -> None:
    event = {
        "request": {
            "method": "GET",
            "url": "https://p.test/privacy/people?email=jane@abc.test",
            "cookies": {"preuve_session": "ses_x"},
            "headers": {"Authorization": "Bearer prv_x"},
            "data": {"password": "hunter2hunter2"},
        },
        "user": {"email": "jane@abc.test"},
    }
    out = _scrub(event, {})
    assert out["request"] == {"method": "GET", "url": "https://p.test/privacy/people"}
    assert "user" not in out
    assert "jane" not in json.dumps(out) and "ses_x" not in json.dumps(out)


def test_json_mode_routes_uvicorn_logs_and_disables_its_access_log(monkeypatch) -> None:
    root = logging.getLogger()
    saved = root.handlers[:], root.level
    try:
        observability.configure_logging("json", "INFO")
        assert isinstance(root.handlers[0].formatter, JsonFormatter)
        assert logging.getLogger("uvicorn.access").disabled
    finally:
        root.handlers[:] = saved[0]
        root.setLevel(saved[1])
        logging.getLogger("uvicorn.access").disabled = False
