"""Phase 5B: deletion leaves nothing behind, no re-import, find/export/erase, retention, check."""

import json
import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.ideas.models import Idea
from app.modules.outreach import service as outreach
from app.modules.privacy import service as privacy
from app.modules.privacy import tombstones
from app.modules.privacy.models import DeletedPerson
from app.modules.prospects import service as prospects
from app.modules.prospects.models import Contact
from app.modules.reports import service as reports
from app.modules.reports.models import Report
from app.modules.research import service as research
from app.modules.research.models import Evidence, ResearchImport, WebSource
from app.modules.responses import service as responses
from app.modules.responses.schemas import ResponsePaste
from app.modules.validation import service as validation
from tests.test_outreach import contact_id
from tests.test_prospects import idea, import_company  # noqa: F401  (fixture)
from tests.test_responses import REPLY, classification, llm_with, sent_message

JANE = "jane@abc.test"


async def _reply_and_report(session: AsyncSession, idea: Idea):
    """Jane got an email, replied, and a report quoting her reply was generated."""
    message = await sent_message(session, idea)  # imports ABC Builders (Jane Roe) too
    r = await responses.create_paste(
        session, idea, ResponsePaste(text=REPLY, message_id=message.id)
    )
    llm, _, _ = llm_with(classification())
    await responses.analyze_response(session, llm, r.id)
    rep = await reports.create(session, idea)
    llm, _, _ = llm_with({"claims": []})
    await reports.generate(session, llm, rep.id)
    await session.refresh(rep)
    assert rep.exhibits  # it quotes Jane's reply
    return r, rep


async def _count(session: AsyncSession, model, *where) -> int:
    return await session.scalar(select(func.count()).select_from(model).where(*where)) or 0


# ---------- deletion leaves nothing behind ----------


async def test_deleting_a_contact_erases_them_everywhere(session: AsyncSession, idea: Idea) -> None:
    _, rep = await _reply_and_report(session, idea)
    cid = await contact_id(session)
    about = await session.scalar(
        select(WebSource).where(WebSource.url == "https://abcbuilders.com/about")
    )
    assert "Jane Roe" in about.full_text
    about_id, rep_id = about.id, rep.id

    assert await prospects.delete_contact(session, idea.id, cid)
    session.expire_all()

    # the quote naming her, any report that quoted her, and her reply are gone
    assert not [e for e in await session.scalars(select(Evidence)) if "Jane" in e.quote]
    assert await session.get(Report, rep_id) is None
    assert await _count(session, Evidence, Evidence.response_id.is_not(None)) == 0
    # quotes that don't name her stay
    assert await _count(session, Evidence, Evidence.quote == "Our team of over 200 employees") == 1
    # the stored page that named her lost its text, but stays traceable
    about = await session.get(WebSource, about_id)
    assert about.text is None and about.full_text is None and about.text_purged_at
    assert about.url and about.fetched_at and about.content_hash
    # the stored research pack no longer mentions her
    for imp in await session.scalars(select(ResearchImport)):
        assert "Jane" not in json.dumps(imp.pack)
    # suppressed, and remembered only as hashes
    assert await outreach.is_suppressed(session, JANE)
    rows = list(await session.scalars(select(DeletedPerson)))
    assert rows and all(JANE not in (r.email_hash or "") for r in rows)
    assert await tombstones.is_deleted(session, email=JANE)
    assert await tombstones.is_deleted(session, domain="abcbuilders.com", name_key="jane roe")


async def test_a_deleted_person_is_not_reimported(session: AsyncSession, idea: Idea) -> None:
    await import_company(session, idea)
    assert await prospects.delete_contact(session, idea.id, await contact_id(session))

    imp = await import_company(session, idea)  # the researcher finds her page again
    assert imp.report["companies"]["contacts_skipped_deleted_on_request"] == 1
    assert "Jane" not in json.dumps(imp.report)
    assert "Jane" not in json.dumps(imp.pack)
    assert await _count(session, Contact) == 0
    assert not [e for e in await session.scalars(select(Evidence)) if "Jane" in e.quote]


async def test_deleting_a_reply_deletes_reports_that_quoted_it(
    session: AsyncSession, idea: Idea
) -> None:
    r, rep = await _reply_and_report(session, idea)
    await responses.delete_response(session, r)
    assert await session.get(Report, rep.id) is None


# ---------- score snapshots hold no personal data ----------


async def test_score_inputs_hold_no_emails_or_names(session: AsyncSession, idea: Idea) -> None:
    r = await responses.create_paste(
        session,
        idea,
        ResponsePaste(text=REPLY, from_name="Dave Gover", from_email="dave@skyline.test"),
    )
    llm, _, _ = llm_with(classification())
    await responses.analyze_response(session, llm, r.id)
    snap = await validation.recompute(session, idea)
    raw = json.dumps(snap.inputs)
    assert "dave" not in raw.lower() and "skyline" not in raw.lower()
    assert snap.facts["validated_conversations"] == 1  # still counted as one customer


# ---------- retention ----------


async def test_page_text_is_dropped_after_30_days(session: AsyncSession, idea: Idea) -> None:
    message = await sent_message(session, idea)
    r = await responses.create_paste(
        session, idea, ResponsePaste(text=REPLY, message_id=message.id)
    )
    llm, _, _ = llm_with(classification())
    await responses.analyze_response(session, llm, r.id)

    now = datetime.now(UTC)
    assert await research.purge_page_text(session, now=now) == 0  # all fresh
    later = now + timedelta(days=31)
    purged = await research.purge_page_text(session, now=later)
    assert purged == await _count(session, WebSource, ~WebSource.url.startswith("preuve://"))
    session.expire_all()
    for src in await session.scalars(select(WebSource)):
        if src.url.startswith("preuve://"):
            assert src.full_text  # a reply's text lives as long as the reply
        else:
            assert src.text is None and src.full_text is None and src.text_purged_at
    # every exhibit is still traceable
    for e in await session.scalars(select(Evidence)):
        src = await session.get(WebSource, e.source_id)
        assert e.quote and src.url and src.fetched_at
    assert await research.purge_page_text(session, now=later) == 0  # idempotent


# ---------- check ----------


async def test_check_is_clean_then_flags_problems(session: AsyncSession, idea: Idea) -> None:
    await import_company(session, idea)
    ws = idea.workspace_id
    assert await privacy.check(session, ws) == []

    contact = await session.scalar(select(Contact))
    contact.collected_at = datetime.now(UTC) - timedelta(days=200)
    contact.email = "jane.roe@gmail.com"
    ev = await session.scalar(
        select(Evidence).where(Evidence.quote == "Our team of over 200 employees")
    )
    ev.quote = " "
    await session.commit()

    kinds = {(f["kind"], f["severity"]) for f in await privacy.check(session, ws)}
    assert ("minimisation", "medium") in kinds  # stale prospect and personal address
    assert ("provenance", "high") in kinds
    findings = await privacy.check(session, ws, now=datetime.now(UTC) + timedelta(days=31))
    assert any(f["kind"] == "retention" for f in findings)
    stale = next(f for f in findings if "never contacted" in f["message"])
    assert stale["contacts"][0]["name"] == "Jane Roe"


# ---------- find, export, erase (API) ----------


async def test_find_export_and_erase_by_email(
    client: AsyncClient, session_maker: async_sessionmaker[AsyncSession]
) -> None:
    created = (
        await client.post("/ideas", json={"title": "t", "description": "d", "target_market": "US"})
    ).json()
    async with session_maker() as s:
        idea = await s.get(Idea, uuid.UUID(created["id"]))
        await _reply_and_report(s, idea)

    found = (await client.get("/privacy/people", params={"email": "JANE@abc.test"})).json()
    assert found["contacts"][0]["name"] == "Jane Roe"
    assert (found["messages"], found["replies"], found["nothing_found"]) == (1, 1, False)

    export = await client.get("/privacy/people/export", params={"email": JANE})
    assert export.status_code == 200 and "attachment" in export.headers["content-disposition"]
    body = export.json()
    assert body["contacts"][0]["source_url"] and body["contact_sources"][0]["quote"]
    assert "We actually have this problem every week" in body["replies"][0]["text"]
    assert body["messages"][0]["body"]

    assert (await client.get("/privacy/people", params={"email": "nope"})).status_code == 422
    erased = (await client.post("/privacy/people/erase", json={"email": JANE})).json()
    assert erased["contacts"] == 1 and erased["replies"] == 1

    after = (await client.get("/privacy/people", params={"email": JANE})).json()
    assert after["contacts"] == [] and after["replies"] == 0 and after["suppressed"] is True
    assert after["nothing_found"] is True  # only the block record remains
    async with session_maker() as s:
        assert await _count(s, Report) == 0
        msg_rows = (await s.execute(text("select to_email, body from messages"))).all()
        assert all(r[0] is None and JANE not in (r[1] or "") for r in msg_rows)


async def test_privacy_endpoints_only_see_the_active_workspace(
    client: AsyncClient, session_maker
) -> None:
    created = (
        await client.post("/ideas", json={"title": "t", "description": "d", "target_market": "US"})
    ).json()
    async with session_maker() as s:
        idea = await s.get(Idea, uuid.UUID(created["id"]))
        await _reply_and_report(s, idea)
    other = (await client.post("/workspaces", json={"name": "Other"})).json()
    await client.post("/auth/workspace", json={"workspace_id": other["id"]})
    found = (await client.get("/privacy/people", params={"email": JANE})).json()
    assert found["nothing_found"] is True
    assert (await client.get("/privacy/check")).json() == {"findings": [], "ok": True}
