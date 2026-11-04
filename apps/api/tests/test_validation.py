"""Validation score from stored rows (PRD §24–§26): inputs, snapshots, state, API."""

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.ideas.models import Idea, ValidationState
from app.modules.interviews import service as interviews
from app.modules.interviews.models import InterviewStatus
from app.modules.interviews.schemas import InterviewUpdate, NoteCreate
from app.modules.research.models import Evidence
from app.modules.responses import service as responses
from app.modules.responses.schemas import ResponsePaste
from app.modules.validation import scoring
from app.modules.validation import service as validation
from app.modules.wtp import service as wtp
from app.modules.wtp.models import Commitment
from app.modules.wtp.schemas import WtpCreate, WtpUpdate
from tests.test_interviews import NOTES, extraction_output, make_interview
from tests.test_prospects import idea  # noqa: F401  (fixture)
from tests.test_responses import REPLY, api_idea, classification, llm_with, sent_message


async def _reply(session: AsyncSession, idea: Idea, **overrides):
    message = await sent_message(session, idea)
    r = await responses.create_paste(
        session, idea, ResponsePaste(text=REPLY, message_id=message.id)
    )
    llm, _, _ = llm_with(classification(**overrides))
    await responses.analyze_response(session, llm, r.id)
    await session.refresh(r)
    return r


async def _done_interview(session: AsyncSession, idea: Idea):
    row = await make_interview(session, idea)
    await interviews.add_note(session, row, NoteCreate(text=NOTES))
    await interviews.start_job(session, row, "extraction")
    llm, _, _ = llm_with(extraction_output())
    await interviews.extract(session, llm, row.id)
    await interviews.update(session, row, InterviewUpdate(status=InterviewStatus.DONE))
    return row


def _dims(row) -> dict:
    return {d["key"]: d for d in row.dimensions}


async def test_one_reply_is_weak_evidence_dont_build_yet(session: AsyncSession, idea: Idea) -> None:
    r = await _reply(session, idea)
    row = await validation.recompute(session, idea)

    assert row.total < 40
    assert row.recommendation == "investigate"
    assert row.decision["headline"] == "Weak evidence. Don't build yet."
    assert row.state == ValidationState.EARLY_SIGNAL
    await session.refresh(idea)
    assert idea.state == ValidationState.EARLY_SIGNAL

    reply_ev = {
        str(e.id)
        for e in await session.scalars(select(Evidence).where(Evidence.response_id == r.id))
    }
    d = _dims(row)
    assert d["problem_evidence"]["points"] >= 3
    assert set(d["problem_evidence"]["evidence_ids"]) & reply_ev
    assert d["frequency"]["points"] == 2 and set(d["frequency"]["evidence_ids"]) <= reply_ev
    assert d["severity"]["points"] == 5  # high (3) + a quantified cost (2)
    assert d["willingness_to_pay"]["points"] == 3  # stated strong, no commitment
    assert any("hasn't committed" in p["text"] for p in row.decision["weak"])
    assert row.decision["next_actions"]
    assert row.metrics["validated_conversations"] == 1


async def test_score_is_reproducible_from_stored_inputs(session: AsyncSession, idea: Idea) -> None:
    await _reply(session, idea)
    a = await validation.recompute(session, idea)
    b = await validation.recompute(session, idea)
    assert a.inputs_hash == b.inputs_hash and a.total == b.total
    assert a.dimensions == b.dimensions and a.decision == b.decision

    again = scoring.evaluate(scoring.from_canonical(a.inputs))
    assert again.inputs_hash == a.inputs_hash
    assert again.total == a.total
    assert again.as_dict()["dimensions"] == a.dimensions


async def test_dismissed_evidence_stops_counting(session: AsyncSession, idea: Idea) -> None:
    r = await _reply(session, idea)
    before = await validation.recompute(session, idea)
    for e in await session.scalars(select(Evidence).where(Evidence.response_id == r.id)):
        e.dismissed = True
    await session.commit()

    assert await validation.current_hash(session, idea) != before.inputs_hash  # now stale
    after = await validation.recompute(session, idea)
    assert _dims(after)["problem_evidence"]["points"] < _dims(before)["problem_evidence"]["points"]
    assert after.metrics["validated_conversations"] == 0


async def test_done_interview_and_commitment_count(session: AsyncSession, idea: Idea) -> None:
    row = await _done_interview(session, idea)
    score = await validation.recompute(session, idea)
    d = _dims(score)
    assert d["interview_confirmation"]["points"] == 5
    assert f"interview:{row.id}" in d["interview_confirmation"]["record_ids"]
    assert d["alternatives"]["points"] >= 2  # workflow quoted
    assert any("objection" in p["text"] for p in score.decision["weak"])

    # A user-recorded pilot is the strongest signal here; stated words alone are not.
    signal = await wtp.create(
        session, idea.id, WtpCreate(customer_label="Jane", contact_id=row.contact_id)
    )
    await wtp.update(session, signal, WtpUpdate(commitment=Commitment.PILOT))
    score = await validation.recompute(session, idea)
    assert _dims(score)["willingness_to_pay"]["points"] == 8


async def test_two_replies_from_one_contact_are_one_customer(
    session: AsyncSession, idea: Idea
) -> None:
    await _reply(session, idea)
    await _reply(
        session,
        idea,
        problem_confirmed={"value": "no", "quote": "We actually have this problem every week"},
    )
    score = await validation.recompute(session, idea)
    # Both replies come from the same sent contact, so they are one customer, who confirmed.
    assert score.facts["confirming_customers"] == 1


async def test_score_api(
    client: AsyncClient, session_maker: async_sessionmaker[AsyncSession]
) -> None:
    idea = await api_idea(client, session_maker)
    base = f"/ideas/{idea.id}"

    empty = (await client.get(f"{base}/score")).json()
    assert empty == {"score": None, "stale": True}

    created = await client.post(f"{base}/score")
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["total"] == 0 and body["state"] == "unvalidated"
    assert body["recommendation"] == "investigate"
    assert body["decision"]["headline"] == "Weak evidence. Don't build yet."
    assert [d["max"] for d in body["dimensions"]] == [20, 10, 15, 15, 15, 10, 15]

    current = (await client.get(f"{base}/score")).json()
    assert current["stale"] is False and current["score"]["id"] == body["id"]
    assert (await client.get(f"/ideas/{idea.id}")).json()["state"] == "unvalidated"

    history = (await client.get(f"{base}/score/history")).json()
    assert [h["id"] for h in history] == [body["id"]]

    assert (await client.get(f"/ideas/{uuid.uuid4()}/score")).status_code == 404
