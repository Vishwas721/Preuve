import uuid

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.analysis import service as analysis
from app.modules.analysis.models import Source, UnknownStatus
from app.modules.analysis.schemas import UnknownCreate, UnknownUpdate
from app.modules.ideas.models import Idea
from app.modules.interviews import prompts
from app.modules.interviews import service as interviews
from app.modules.interviews.models import JobState
from app.modules.interviews.schemas import InterviewCreate, NoteCreate
from app.modules.prospects import service as prospects
from app.modules.research.models import Evidence, EvidenceOrigin, EvidenceUnknown
from app.modules.wtp import service as wtp
from app.modules.wtp.models import Commitment, WtpSource
from app.modules.wtp.schemas import WtpCreate, WtpUpdate
from tests.test_outreach import contact_id
from tests.test_prospects import idea, import_company  # noqa: F401  (fixture)
from tests.test_responses import api_idea, llm_with

NOTES = (
    "Called Jane, 30 min. She said the weekly owner report takes her team about half a day. "
    "Photos come in over WhatsApp and get pasted into a Word template. "
    "The owner's rep signs off on the report before the pay application goes out. "
    "Her concern: the field team won't adopt another app."
)


async def add_unknowns(session: AsyncSession, idea: Idea) -> list[uuid.UUID]:
    rows = [
        analysis.add_unknown(
            session, idea.id, UnknownCreate(question=q, category=c, priority="high"), Source.USER
        )
        for q, c in [
            ("Who approves the weekly report?", "buyer"),
            ("How long does the report take?", "cost"),
            ("What tools are used today?", "current_solution"),
        ]
    ]
    await session.commit()
    return [r.id for r in rows]


async def make_interview(session: AsyncSession, idea: Idea) -> interviews.Interview:
    await import_company(session, idea)
    return await interviews.create(
        session, idea, InterviewCreate(contact_id=await contact_id(session))
    )


def guide_output(**overrides) -> dict:
    out = {
        "questions": [
            {
                "unknown_ref": "U1",
                "question": "Walk me through what happens after the report is finished.",
                "follow_ups": ["Who looks at it next?"],
            },
            {
                "unknown_ref": "U2",
                "question": "Would you say the report takes too long?",  # leading yes/no
                "follow_ups": [],
            },
            {
                "unknown_ref": "U9",
                "question": "Tell me about your budget process.",
                "follow_ups": [],
            },
        ]
    }
    return out | overrides


def extraction_output(**overrides) -> dict:
    out = {
        "problem": {
            "value": "slow weekly report",
            "quote": "the weekly owner report takes her team about half a day",
        },
        "workflow": {
            "value": "WhatsApp photos into Word",
            "quote": "Photos come in over WhatsApp and get pasted into a Word template",
        },
        "objections": {"value": "adoption", "quote": "the field team won't adopt another app"},
        "cost": {"value": "a whole day", "quote": "it takes a whole day"},  # not in notes
        "answered_unknowns": [
            {
                "unknown_ref": "U1",
                "answer": "The owner's rep signs off.",
                "quote": "The owner's rep signs off on the report",
            },
            {"unknown_ref": "U7", "answer": "n/a", "quote": "anything"},
        ],
        "willingness_to_pay": {"value": "unknown", "quote": ""},
    }
    return out | overrides


# ---------- leading-question checks ----------


def test_question_flags() -> None:
    assert prompts.question_flags("Tell me about the last time you wrote the report.") == []
    assert prompts.question_flags("Walk me through how you handle photos today.") == []
    assert prompts.question_flags("Do you find reporting hard?")
    assert prompts.question_flags("Would you pay for a tool that automates it?")
    assert prompts.question_flags("Wouldn't it be great to skip this?")
    assert prompts.question_flags("How painful is the report?")
    assert prompts.question_flags("What tools? And who pays?")


# ---------- guide ----------


async def test_guide_uses_only_open_unknowns(session: AsyncSession, idea: Idea) -> None:
    u1, u2, u3 = await add_unknowns(session, idea)
    await analysis.update_unknown(
        session,
        await analysis.get_unknown(session, idea.id, u3),
        UnknownUpdate(status=UnknownStatus.ANSWERED),
    )
    row = await make_interview(session, idea)
    assert row.interviewee_name == "Jane Roe" and row.company_name == "ABC Builders"

    llm, local, gemini = llm_with(guide_output())
    assert await interviews.generate_guide(session, llm, row.id) == JobState.DONE
    prompt = local.calls[0].prompt
    assert (
        "Who approves the weekly report?" in prompt and "What tools are used today?" not in prompt
    )
    assert not gemini.calls

    await session.refresh(row)
    qs = row.guide["questions"]
    assert [q["unknown_id"] for q in qs] == [str(u1), str(u2)]  # U9 isn't an open unknown
    assert row.guide["skipped"] == 1
    assert qs[0]["flags"] == [] and qs[1]["flags"]  # the leading one is flagged
    assert row.guide["uncovered"] == []


async def test_guide_with_no_open_unknowns(session: AsyncSession, idea: Idea) -> None:
    row = await make_interview(session, idea)
    llm, local, _ = llm_with()
    assert await interviews.generate_guide(session, llm, row.id) == JobState.DONE
    assert not local.calls
    await session.refresh(row)
    assert row.guide["questions"] == []


# ---------- extraction ----------


async def test_extraction_records_only_verified_quotes(session: AsyncSession, idea: Idea) -> None:
    u1, *_ = await add_unknowns(session, idea)
    row = await make_interview(session, idea)
    await interviews.add_note(session, row, NoteCreate(text=NOTES))
    await interviews.start_job(session, row, "extraction")

    llm, local, gemini = llm_with(extraction_output())
    assert await interviews.extract(session, llm, row.id) == JobState.DONE
    assert NOTES[:40] in local.calls[0].prompt and not gemini.calls

    await session.refresh(row)
    ev = list(await session.scalars(select(Evidence).where(Evidence.interview_id == row.id)))
    assert all(e.origin == EvidenceOrigin.INTERVIEW and e.quote in NOTES for e in ev)
    quotes = {e.quote for e in ev}
    assert "it takes a whole day" not in quotes
    assert {d["quote"] for d in row.dropped} == {"it takes a whole day"}
    assert row.extraction["cost"]["quote"] == ""
    stances = {e.statement.split(": ")[1]: e.stance for e in ev if ": " in e.statement}
    assert stances.get("objections") == "contradicts"

    [proposal] = row.extraction["answered_unknowns"]  # U7 isn't an open unknown
    assert proposal["unknown_id"] == str(u1) and not proposal["confirmed"]

    # The user confirms: the evidence is linked and the unknown is answered.
    await interviews.confirm_unknown(session, row, u1)
    unknown = await analysis.get_unknown(session, idea.id, u1)
    assert unknown.status == UnknownStatus.ANSWERED
    link = await session.scalar(select(EvidenceUnknown).where(EvidenceUnknown.unknown_id == u1))
    assert str(link.evidence_id) == proposal["evidence_id"]
    await session.refresh(row)
    assert row.extraction["answered_unknowns"][0]["confirmed"]


async def test_extraction_needs_notes_and_proposes_wtp(session: AsyncSession, idea: Idea) -> None:
    row = await make_interview(session, idea)
    try:
        await interviews.start_job(session, row, "extraction")
        raise AssertionError("expected InterviewError")
    except interviews.InterviewError:
        pass
    await interviews.add_note(
        session,
        row,
        NoteCreate(text="She said: we'd pay for this if it saved the Friday afternoon."),
    )
    out = extraction_output(
        answered_unknowns=[],
        willingness_to_pay={
            "value": "some",
            "quote": "we'd pay for this if it saved the Friday afternoon",
        },
    )
    llm, _, _ = llm_with(out)
    await interviews.extract(session, llm, row.id)
    [signal] = await wtp.list_signals(session, idea.id)
    assert signal.stated_willingness == "some" and signal.commitment == Commitment.NONE
    assert signal.source == WtpSource.AI and signal.interview_id == row.id


async def test_delete_contact_removes_interviews(session: AsyncSession, idea: Idea) -> None:
    row = await make_interview(session, idea)
    await interviews.add_note(session, row, NoteCreate(text=NOTES))
    llm, _, _ = llm_with(extraction_output(answered_unknowns=[]))
    await interviews.extract(session, llm, row.id)
    iid = row.id
    assert await prospects.delete_contact(session, idea.id, await contact_id(session))
    session.expire_all()
    assert await session.get(interviews.Interview, iid) is None
    assert (
        await session.scalar(
            select(func.count()).select_from(Evidence).where(Evidence.origin == "interview")
        )
        == 0
    )


# ---------- WTP ----------


async def test_ai_cannot_set_a_commitment(session: AsyncSession, idea: Idea) -> None:
    proposal = await wtp.propose(
        session,
        idea_id=idea.id,
        customer_label="Jane",
        stated="strong",
        quote="I'd pay for it",
        evidence_id=None,
    )
    assert proposal.commitment == Commitment.NONE and proposal.committed_at is None
    assert (
        await wtp.propose(
            session,
            idea_id=idea.id,
            customer_label="x",
            stated="unknown",
            quote="q",
            evidence_id=None,
        )
        is None
    )
    # Only a user edit records a commitment, and it gets a date.
    await wtp.update(
        session, proposal, WtpUpdate(commitment=Commitment.SIGNED, commitment_note="LOI")
    )
    assert proposal.commitment == "signed" and proposal.committed_at is not None
    assert proposal.stated_willingness == "strong"  # stated stays separate
    await wtp.update(session, proposal, WtpUpdate(commitment=Commitment.NONE))
    assert proposal.committed_at is None


# ---------- API ----------


async def test_interviews_and_wtp_api(
    client: AsyncClient, session_maker: async_sessionmaker[AsyncSession], queue
) -> None:
    idea = await api_idea(client, session_maker)
    async with session_maker() as session:
        await add_unknowns(session, idea)
        row = await make_interview(session, idea)
    base = f"/ideas/{idea.id}"

    assert (await client.post(f"{base}/interviews", json={})).status_code == 422
    r = await client.post(
        f"{base}/interviews", json={"interviewee_name": "Sam", "interviewee_role": "CFO"}
    )
    assert r.status_code == 201 and r.json()["guide_state"] == "none"

    r = await client.post(f"{base}/interviews/{row.id}/guide")
    assert r.status_code == 200 and r.json()["guide_state"] == "queued"
    assert queue.jobs[-1] == ("interview_guide", (str(row.id),))
    assert (await client.post(f"{base}/interviews/{row.id}/guide")).status_code == 409

    assert (await client.post(f"{base}/interviews/{row.id}/extract")).status_code == 409  # no notes
    r = await client.post(f"{base}/interviews/{row.id}/notes", json={"text": NOTES})
    [note] = r.json()["notes"]
    r = await client.post(f"{base}/interviews/{row.id}/extract")
    assert r.json()["extraction_state"] == "queued"
    assert queue.jobs[-1] == ("analyze_interview", (str(row.id),))

    async with session_maker() as session:
        llm, _, _ = llm_with(extraction_output())
        await interviews.extract(session, llm, row.id)
    detail = (await client.get(f"{base}/interviews/{row.id}")).json()
    assert detail["extraction_state"] == "done" and detail["evidence_ids"]
    uid = detail["extraction"]["answered_unknowns"][0]["unknown_id"]
    r = await client.post(f"{base}/interviews/{row.id}/unknowns/{uid}/confirm")
    assert r.json()["extraction"]["answered_unknowns"][0]["confirmed"]
    bogus = await client.post(f"{base}/interviews/{row.id}/unknowns/{uuid.uuid4()}/confirm")
    assert bogus.status_code == 409

    r = await client.patch(f"{base}/interviews/{row.id}", json={"status": "done"})
    assert r.json()["status"] == "done"
    assert (await client.get(f"{base}/responses/dashboard")).json()["interviews_done"] == 1

    assert (await client.delete(f"{base}/interviews/{row.id}/notes/{note['id']}")).json()[
        "notes"
    ] == []

    # WTP ledger
    r = await client.post(
        f"{base}/wtp",
        json={
            "customer_label": "Sam, CFO",
            "stated_willingness": "some",
            "expected_price": "$200/mo",
        },
    )
    assert (
        r.status_code == 201 and r.json()["commitment"] == "none" and r.json()["source"] == "user"
    )
    wid = r.json()["id"]
    r = await client.patch(
        f"{base}/wtp/{wid}", json={"commitment": "pilot", "commitment_note": "2-site pilot"}
    )
    assert r.json()["commitment"] == "pilot" and r.json()["committed_at"]
    assert len((await client.get(f"{base}/wtp")).json()) == 1
    assert (await client.delete(f"{base}/wtp/{wid}")).status_code == 204
    bad = await client.post(
        f"{base}/wtp", json={"customer_label": "x", "contact_id": str(uuid.uuid4())}
    )
    assert bad.status_code == 422

    assert (await client.delete(f"{base}/interviews/{row.id}")).status_code == 204
    assert (await client.get(f"{base}/interviews/{row.id}")).status_code == 404


async def test_wtp_create_service(session: AsyncSession, idea: Idea) -> None:
    await import_company(session, idea)
    row = await wtp.create(
        session,
        idea.id,
        WtpCreate(customer_label="Jane", contact_id=await contact_id(session), commitment="verbal"),
    )
    assert row.company_id is not None and row.committed_at is not None


async def test_quoted_field_without_value_is_kept(session: AsyncSession, idea: Idea) -> None:
    row = await make_interview(session, idea)
    await interviews.add_note(session, row, NoteCreate(text=NOTES))
    out = extraction_output(
        objections={"value": "", "quote": "the field team won't adopt another app"},
        frequency={"value": "half a day", "quote": ""},  # verbatim value, no quote
        answered_unknowns=[],
    )
    llm, _, _ = llm_with(out)
    await interviews.extract(session, llm, row.id)
    quotes = set(
        await session.scalars(select(Evidence.quote).where(Evidence.interview_id == row.id))
    )
    assert "the field team won't adopt another app" in quotes
    assert "half a day" in quotes


def test_question_flags_calibrated_on_live_guide() -> None:
    """Cases from the live qwen2.5 guide: open prompts pass, real yes/no questions don't."""
    assert prompts.question_flags("Can you walk me through the process from start to finish?") == []
    assert prompts.question_flags("Could you tell me about the last report you wrote?") == []
    assert prompts.question_flags(
        "Do general contractors that don't use Procore have a painful reporting workflow?"
    )
    assert prompts.question_flags("Is this time consistent across different projects?")
    assert prompts.question_flags("Could this be automated?")


async def test_non_answers_are_skipped_not_dropped(session: AsyncSession, idea: Idea) -> None:
    u1, u2, _ = await add_unknowns(session, idea)
    row = await make_interview(session, idea)
    await interviews.add_note(session, row, NoteCreate(text=NOTES))
    out = extraction_output(
        cost={"value": "", "quote": ""},
        answered_unknowns=[
            {
                "unknown_ref": "U1",
                "answer": "The owner's rep signs off.",
                "quote": "The owner's rep signs off on the report",
            },
            {"unknown_ref": "U2", "answer": "Not provided in the notes.", "quote": "'"},
        ],
    )
    llm, _, _ = llm_with(out)
    await interviews.extract(session, llm, row.id)
    await session.refresh(row)
    assert [a["unknown_id"] for a in row.extraction["answered_unknowns"]] == [str(u1)]
    assert row.dropped == []


async def test_wrapped_quotes_are_unwrapped(session: AsyncSession, idea: Idea) -> None:
    """Live qwen2.5 output: quotes wrapped in single quotes still verify against the notes."""
    row = await make_interview(session, idea)
    await interviews.add_note(session, row, NoteCreate(text=NOTES))
    out = extraction_output(
        objections={"value": "", "quote": "'the field team won't adopt another app'"},
        workflow={"value": "", "quote": "“Photos come in over WhatsApp”"},
        cost={"value": "", "quote": ""},
        answered_unknowns=[],
    )
    llm, _, _ = llm_with(out)
    await interviews.extract(session, llm, row.id)
    await session.refresh(row)
    quotes = set(
        await session.scalars(select(Evidence.quote).where(Evidence.interview_id == row.id))
    )
    assert {"the field team won't adopt another app", "Photos come in over WhatsApp"} <= quotes
    assert row.dropped == []
    assert row.extraction["objections"]["quote"] == "the field team won't adopt another app"
