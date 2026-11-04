"""Interviews (PRD §21–§22).

- The guide is built only from open unknowns; each question cites its unknown and is checked
  for leading wording.
- Notes are private: extraction runs with `private=True`. Only verbatim-quoted fields become
  first-party evidence; answered unknowns are proposed, and the user confirms each one.
"""

import logging
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import LLMError
from app.llm.router import LLMRouter
from app.llm.tasks import TaskType
from app.modules.analysis import service as analysis
from app.modules.analysis.models import UnknownStatus
from app.modules.analysis.schemas import UnknownUpdate
from app.modules.ideas.models import Idea
from app.modules.interviews import prompts
from app.modules.interviews.models import (
    Interview,
    InterviewNote,
    InterviewStatus,
    JobState,
)
from app.modules.interviews.schemas import InterviewCreate, InterviewUpdate, NoteCreate
from app.modules.prospects import service as prospects
from app.modules.research import firstparty
from app.modules.research import service as research
from app.modules.research.models import EvidenceOrigin
from app.modules.research.pack import FindingStatus, Relevance, Stance
from app.modules.wtp import service as wtp
from app.modules.wtp.models import StatedWillingness

logger = logging.getLogger(__name__)

MAX_KNOWN = 6
ACTIVE = (JobState.QUEUED, JobState.RUNNING)


class InterviewError(Exception):
    pass


# ---------- records ----------


async def create(session: AsyncSession, idea: Idea, data: InterviewCreate) -> Interview:
    fields = data.model_dump()
    company_id = None
    if data.contact_id is not None:
        found = await prospects.get_contact(session, idea.id, data.contact_id)
        if found is None:
            raise InterviewError("Contact not found on this idea")
        contact, company = found
        fields["interviewee_name"] = fields["interviewee_name"] or contact.name
        fields["interviewee_role"] = fields["interviewee_role"] or contact.role
        fields["company_name"] = fields["company_name"] or company.name
        company_id = company.id
    if not fields["interviewee_name"].strip():
        raise InterviewError("Who is the interview with? Pick a contact or enter a name.")
    if data.response_id is not None:
        from app.modules.responses import service as responses  # lazy: responses imports us

        if await responses.get_response(session, idea.id, data.response_id) is None:
            raise InterviewError("Reply not found on this idea")
    row = Interview(idea_id=idea.id, company_id=company_id, **fields)
    session.add(row)
    await session.commit()
    return row


async def update(session: AsyncSession, row: Interview, data: InterviewUpdate) -> Interview:
    for k, v in data.model_dump(exclude_unset=True).items():
        if v is not None or k == "scheduled_at":
            setattr(row, k, v)
    await session.commit()
    return row


async def list_interviews(session: AsyncSession, idea_id: uuid.UUID) -> list[Interview]:
    return list(
        await session.scalars(
            select(Interview)
            .where(Interview.idea_id == idea_id)
            .order_by(Interview.scheduled_at.desc().nulls_first(), Interview.created_at.desc())
        )
    )


async def get_interview(
    session: AsyncSession, idea_id: uuid.UUID, interview_id: uuid.UUID
) -> Interview | None:
    return await session.scalar(
        select(Interview).where(Interview.id == interview_id, Interview.idea_id == idea_id)
    )


async def notes(session: AsyncSession, interview_id: uuid.UUID) -> list[InterviewNote]:
    return list(
        await session.scalars(
            select(InterviewNote)
            .where(InterviewNote.interview_id == interview_id)
            .order_by(InterviewNote.created_at)
        )
    )


async def detail(session: AsyncSession, row: Interview) -> dict[str, Any]:
    await session.refresh(row)
    data = {c.key: getattr(row, c.key) for c in Interview.__table__.columns}
    data["notes"] = await notes(session, row.id)
    data["evidence_ids"] = await research.evidence_ids_for(
        session, row.idea_id, interview_id=row.id
    )
    return data


async def add_note(session: AsyncSession, row: Interview, data: NoteCreate) -> InterviewNote:
    note = InterviewNote(interview_id=row.id, kind=data.kind, text=data.text.strip())
    session.add(note)
    await session.commit()
    return note


async def delete_note(session: AsyncSession, row: Interview, note_id: uuid.UUID) -> bool:
    note = await session.get(InterviewNote, note_id)
    if note is None or note.interview_id != row.id:
        return False
    await session.delete(note)
    await session.commit()
    return True


async def delete_interview(session: AsyncSession, row: Interview) -> None:
    await _drop(session, [row])
    await session.commit()


async def count_done(session: AsyncSession, idea_id: uuid.UUID) -> int:
    return (
        await session.scalar(
            select(func.count()).where(
                Interview.idea_id == idea_id, Interview.status == InterviewStatus.DONE
            )
        )
        or 0
    )


# ---------- unknowns ----------


async def _open_unknowns(
    session: AsyncSession, idea_id: uuid.UUID
) -> tuple[list[prompts.UnknownItem], dict[str, uuid.UUID]]:
    rows = [
        u for u in await analysis.list_unknowns(session, idea_id) if u.status == UnknownStatus.OPEN
    ]
    refs = {f"U{i}": u.id for i, u in enumerate(rows, 1)}
    items = [
        prompts.UnknownItem(ref, u.question, u.category.value)
        for ref, u in zip(refs, rows, strict=True)
    ]
    return items, refs


async def _known(session: AsyncSession, idea_id: uuid.UUID) -> list[dict[str, Any]]:
    """What research already established: cited fact/inference claims from answered findings."""
    known: list[dict[str, Any]] = []
    for f in await research.latest_findings(session, idea_id):
        if f.status not in (FindingStatus.ANSWERED, FindingStatus.PARTIALLY_ANSWERED):
            continue
        for claim in f.summary:
            if claim.get("kind") in ("fact", "inference") and claim.get("evidence_ids"):
                known.append(claim)
    return known[:MAX_KNOWN]


# ---------- guide ----------


async def start_job(session: AsyncSession, row: Interview, which: str) -> None:
    state = row.guide_state if which == "guide" else row.extraction_state
    if state in ACTIVE:
        raise InterviewError(f"The {which} is already being prepared")
    if which == "extraction" and not await notes(session, row.id):
        raise InterviewError("Add notes before extracting")
    if which == "guide":
        row.guide_state = JobState.QUEUED
    else:
        row.extraction_state = JobState.QUEUED
    row.error = None
    await session.commit()


async def mark_failed(
    session: AsyncSession, interview_id: uuid.UUID, which: str, error: str
) -> None:
    row = await session.get(Interview, interview_id)
    if row is None:
        return
    if which == "guide" and row.guide_state in ACTIVE:
        row.guide_state = JobState.FAILED
    elif which == "extraction" and row.extraction_state in ACTIVE:
        row.extraction_state = JobState.FAILED
    row.error = error
    await session.commit()


async def generate_guide(
    session: AsyncSession, llm: LLMRouter, interview_id: uuid.UUID
) -> JobState | None:
    row = await session.get(Interview, interview_id)
    if row is None:
        return None
    row.guide_state = JobState.RUNNING
    await session.commit()

    items, refs = await _open_unknowns(session, row.idea_id)
    known = await _known(session, row.idea_id)
    if not items:
        row.guide = {"known": known, "questions": [], "note": "No open unknowns to ask about."}
        row.guide_state = JobState.DONE
        await session.commit()
        return row.guide_state

    hypothesis = await analysis.get_current_hypothesis(session, row.idea_id)
    idea = await session.get(Idea, row.idea_id)
    who = row.interviewee_name + (f", {row.interviewee_role}" if row.interviewee_role else "")
    try:
        draft = await llm.structured(
            TaskType.INTERVIEW_GUIDE,
            prompts.build_guide_prompt(
                hypothesis.problem if hypothesis else idea.description, who, items
            ),
            prompts.GuideDraft,
            system=prompts.GUIDE_SYSTEM,
            temperature=0.3,
        )
    except LLMError as exc:
        row.guide_state, row.error = JobState.FAILED, f"Couldn't write a guide ({exc})."
        await session.commit()
        return row.guide_state

    questions, skipped = [], 0
    by_ref = {i.ref: i for i in items}
    for q in draft.questions:
        if q.unknown_ref not in refs:  # only open unknowns: anything else is dropped
            skipped += 1
            continue
        questions.append(
            {
                "unknown_id": str(refs[q.unknown_ref]),
                "unknown": by_ref[q.unknown_ref].question,
                "question": q.question.strip(),
                "follow_ups": [f.strip() for f in q.follow_ups if f.strip()],
                "flags": prompts.question_flags(q.question),
                "follow_up_flags": [prompts.question_flags(f) for f in q.follow_ups],
            }
        )
    covered = {q["unknown_id"] for q in questions}
    row.guide = {
        "known": known,
        "questions": questions,
        "uncovered": [
            {"unknown_id": str(refs[i.ref]), "unknown": i.question}
            for i in items
            if str(refs[i.ref]) not in covered
        ],
        "skipped": skipped,
    }
    row.guide_state = JobState.DONE
    await session.commit()
    return row.guide_state


# ---------- extraction ----------

_STANCE = {
    "problem": Stance.SUPPORTS,
    "frequency": Stance.SUPPORTS,
    "cost": Stance.SUPPORTS,
    "trigger": Stance.SUPPORTS,
    "objections": Stance.CONTRADICTS,
}


def _notes_text(rows: list[InterviewNote]) -> str:
    return "\n\n".join(n.text for n in rows)


async def extract(
    session: AsyncSession, llm: LLMRouter, interview_id: uuid.UUID
) -> JobState | None:
    row = await session.get(Interview, interview_id)
    if row is None:
        return None
    row.extraction_state = JobState.RUNNING
    await session.commit()

    text = _notes_text(await notes(session, row.id))
    items, refs = await _open_unknowns(session, row.idea_id)
    try:
        out = await llm.structured(
            TaskType.EXTRACT_FIELDS,
            prompts.build_extract_prompt(text, items),
            prompts.InterviewExtraction,
            system=prompts.EXTRACT_SYSTEM,
            private=True,
        )
    except LLMError as exc:
        row.extraction_state = JobState.FAILED
        row.error = f"Couldn't extract from the notes ({exc})."
        await session.commit()
        return row.extraction_state

    who = row.interviewee_name
    sigs: list[firstparty.Signal] = []
    for field, label in prompts.FIELDS:
        item = getattr(out, field)
        item.quote = firstparty.recover_quote(item.value, item.quote, text)
        if item.quote:
            # A quote with no summary still counts: the statement then is the quote itself.
            summary = item.value.strip() or item.quote
            sigs.append(
                firstparty.Signal(
                    f"{who} (interview): {label.lower()}: {summary}",
                    item.quote,
                    _STANCE.get(field, Stance.NEUTRAL),
                    Relevance.HIGH,
                )
            )
    by_ref = {i.ref: i for i in items}
    for a in out.answered_unknowns:
        a.quote = firstparty.clean_quote(a.quote)
    out.willingness_to_pay.quote = firstparty.clean_quote(out.willingness_to_pay.quote)
    answers = [
        a
        for a in out.answered_unknowns
        if a.unknown_ref in refs and not prompts.is_non_answer(a.answer, a.quote)
    ]
    for a in answers:
        sigs.append(
            firstparty.Signal(
                f"{who} (interview) on “{by_ref[a.unknown_ref].question}”: {a.answer.strip()}",
                a.quote,
                Stance.NEUTRAL,
                Relevance.HIGH,
            )
        )
    wtp_q = out.willingness_to_pay
    if wtp_q.quote.strip() and wtp_q.value.value != "unknown":
        sigs.append(
            firstparty.Signal(
                f"{who} (interview): willingness to pay: {wtp_q.value.value}",
                wtp_q.quote,
                Stance.CONTRADICTS if wtp_q.value.value == "none" else Stance.SUPPORTS,
                Relevance.HIGH,
            )
        )

    # Answers the user already confirmed survive re-extraction: their quotes are recorded
    # again (the unknown is no longer open, so the model won't propose it a second time).
    kept = [p for p in (row.extraction or {}).get("answered_unknowns", []) if p.get("confirmed")]
    for p in kept:
        sigs.append(
            firstparty.Signal(
                f"{who} (interview) on “{p['unknown']}”: {p['answer']}",
                p["quote"],
                Stance.NEUTRAL,
                Relevance.HIGH,
            )
        )

    evidence_ids, dropped = await firstparty.record(
        session,
        idea_id=row.idea_id,
        origin=EvidenceOrigin.INTERVIEW,
        owner_id=row.id,
        title=f"Interview with {who}" + (f", {row.company_name}" if row.company_name else ""),
        text=text,
        at=row.scheduled_at or row.created_at,
        signals=sigs,
        company_name=row.company_name or None,
    )
    if row.company_id:
        await prospects.link_company_evidence(session, row.company_id, evidence_ids)
    bad = {d["quote"] for d in dropped}

    data = out.model_dump(mode="json", exclude={"answered_unknowns"})
    for field, _ in prompts.FIELDS:
        if data[field]["quote"].strip() in bad:
            data[field]["quote"] = ""
    proposals = []
    for p in kept:
        eid = await research.evidence_for_quote(session, row.idea_id, evidence_ids, p["quote"])
        unknown = await analysis.get_unknown(session, row.idea_id, uuid.UUID(p["unknown_id"]))
        if eid is not None and unknown is not None:
            await firstparty.link_unknown(session, [eid], unknown.id)
            proposals.append({**p, "evidence_id": str(eid)})
        elif unknown is not None and unknown.status == UnknownStatus.ANSWERED:
            # The notes no longer contain the words it was answered with: reopen it.
            await analysis.set_unknown_status(session, unknown, UnknownStatus.OPEN)
    kept_quotes = {p["quote"] for p in kept}
    dropped = [d for d in dropped if d["quote"] not in kept_quotes]
    for a in answers:
        if a.quote.strip() in bad:
            continue
        eid = await research.evidence_for_quote(session, row.idea_id, evidence_ids, a.quote)
        proposals.append(
            {
                "unknown_id": str(refs[a.unknown_ref]),
                "unknown": by_ref[a.unknown_ref].question,
                "answer": a.answer.strip(),
                "quote": a.quote.strip(),
                "evidence_id": str(eid) if eid else None,
                "confirmed": False,
            }
        )
    data["answered_unknowns"] = proposals

    if wtp_q.quote.strip() and wtp_q.quote.strip() not in bad:
        await wtp.propose(
            session,
            idea_id=row.idea_id,
            customer_label=who + (f", {row.company_name}" if row.company_name else ""),
            stated=StatedWillingness(wtp_q.value.value),
            quote=wtp_q.quote,
            evidence_id=await research.evidence_for_quote(
                session, row.idea_id, evidence_ids, wtp_q.quote
            ),
            contact_id=row.contact_id,
            company_id=row.company_id,
            interview_id=row.id,
        )

    row.extraction, row.dropped = data, dropped
    row.extraction_state = JobState.DONE
    await session.commit()
    return row.extraction_state


async def confirm_unknown(session: AsyncSession, row: Interview, unknown_id: uuid.UUID) -> None:
    """The user confirms an answered unknown proposed by the extraction."""
    proposals = (row.extraction or {}).get("answered_unknowns", [])
    match = next((p for p in proposals if p["unknown_id"] == str(unknown_id)), None)
    if match is None:
        raise InterviewError("The extraction didn't propose an answer for this unknown")
    unknown = await analysis.get_unknown(session, row.idea_id, unknown_id)
    if unknown is None:
        raise InterviewError("Unknown not found")
    if match.get("evidence_id"):
        await firstparty.link_unknown(session, [uuid.UUID(match["evidence_id"])], unknown.id)
    row.extraction = {
        **row.extraction,
        "answered_unknowns": [{**p, "confirmed": True} if p is match else p for p in proposals],
    }
    await analysis.update_unknown(session, unknown, UnknownUpdate(status=UnknownStatus.ANSWERED))


# ---------- deletion ----------


async def _drop(session: AsyncSession, rows: list[Interview]) -> None:
    companies = {r.company_id for r in rows if r.company_id}
    for row in rows:
        # Only open unknowns can be proposed, so a confirmed answer moved it open -> answered;
        # with the interview gone, that answer is withdrawn.
        for p in (row.extraction or {}).get("answered_unknowns", []):
            if not p.get("confirmed"):
                continue
            unknown = await analysis.get_unknown(session, row.idea_id, uuid.UUID(p["unknown_id"]))
            if unknown is not None and unknown.status == UnknownStatus.ANSWERED:
                await analysis.set_unknown_status(session, unknown, UnknownStatus.OPEN)
        await firstparty.clear(session, row.idea_id, EvidenceOrigin.INTERVIEW, row.id)
        await wtp.forget_interview(session, row.id)
        await session.delete(row)  # notes cascade
    await session.flush()
    for cid in companies:
        await prospects.rescore_company_id(session, cid)


async def forget_contact(session: AsyncSession, contact_id: uuid.UUID) -> None:
    """Deletion request (PRD §37): delete this person's interviews, notes and their evidence."""
    rows = await session.scalars(select(Interview).where(Interview.contact_id == contact_id))
    await _drop(session, list(rows))
