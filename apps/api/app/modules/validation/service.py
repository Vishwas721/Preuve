"""Builds the scoring inputs from stored rows and keeps score snapshots (PRD §24–§27).

Reads other modules only through their service functions. Only evidence that is stored and not
dismissed counts; first-party signals are tied to their evidence rows by quote.
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analysis import service as analysis
from app.modules.analysis.models import UnknownStatus
from app.modules.competitors import service as competitors
from app.modules.ideas.models import Idea, ValidationState
from app.modules.interviews import service as interviews
from app.modules.outreach import service as outreach
from app.modules.research import service as research
from app.modules.research.matching import quote_key
from app.modules.research.pack import domain_key
from app.modules.responses import service as responses
from app.modules.validation import scoring
from app.modules.validation.models import ValidationScore
from app.modules.wtp import service as wtp

# Reply classification field -> scoring field. Values are kept for labelled fields.
_REPLY_FIELDS = {
    "problem_confirmed": "problem_confirmed",
    "pain": "pain",
    "frequency": "frequency",
    "current_solution": "current_solution",
    "time_or_cost": "cost",
    "severity": "severity",
    "solution_satisfaction": "solution_satisfaction",
    "interest": "interest",
    "willingness_to_pay": "wtp_stated",
}
_LABELLED = {"problem_confirmed", "severity", "solution_satisfaction", "interest", "wtp_stated"}
# Interview extraction field -> scoring field (the customer describing the problem confirms it).
_INTERVIEW_FIELDS = {
    "problem": ("problem_confirmed", "yes"),
    "workflow": ("current_solution", ""),
    "alternatives": ("current_solution", ""),
    "frequency": ("frequency", ""),
    "cost": ("cost", ""),
    "objections": ("objection", ""),
    "trigger": ("trigger", ""),
    "buyer": ("buyer", ""),
    "decision_process": ("decision_process", ""),
    "desired_solution": ("desired_solution", ""),
    "willingness_to_pay": ("wtp_stated", None),
}


def _norm(text: str | None) -> str:
    return " ".join((text or "").lower().split())


def _person_key(contact_id, company_id, fallback: str) -> str:
    if contact_id:
        return f"contact:{contact_id}"
    if company_id:
        return f"company:{company_id}"
    return f"name:{_norm(fallback)}"


def _company_key(company_id, company_name: str | None, customer: str) -> str:
    if company_id:
        return f"company:{company_id}"
    if _norm(company_name):
        return f"name:{_norm(company_name)}"
    return customer


def _field_signals(
    fields: dict[str, Any],
    mapping: dict[str, tuple[str, str | None]],
    by_key: dict[str, str],
    **common: str,
) -> list[scoring.CustomerSignal]:
    """One signal per stored field whose quote is a counted evidence row of this owner."""
    out = []
    for name, (target, fixed) in mapping.items():
        item = fields.get(name) or {}
        quote = (item.get("quote") or "").strip()
        eid = by_key.get(quote_key(quote)) if quote else None
        if eid is None:
            continue
        value = fixed if fixed is not None else _norm(str(item.get("value", "")))
        out.append(scoring.CustomerSignal(evidence_id=eid, field=target, value=value, **common))
    return out


async def build_input(session: AsyncSession, idea: Idea) -> scoring.ValidationInput:
    evidence = await research.list_evidence(session, idea.id)  # not dismissed
    unknowns = await analysis.list_unknowns(session, idea.id)
    category = {u.id: u.category.value for u in unknowns}

    research_items = []
    first_party: dict[uuid.UUID, dict[str, str]] = {}  # owner id -> quote key -> evidence id
    for e in evidence:
        if e["origin"].value == "research":
            research_items.append(
                scoring.ResearchItem(
                    evidence_id=str(e["id"]),
                    domain=domain_key(e["final_url"] or e["url"]),
                    stance=e["stance"].value,
                    relevance=e["relevance"].value,
                    verification=e["verification"].value,
                    unknown_categories=tuple(
                        sorted({category[u] for u in e["unknown_ids"] if u in category})
                    ),
                )
            )
        else:
            owner = e["response_id"] or e["interview_id"]
            first_party.setdefault(owner, {})[quote_key(e["quote"])] = str(e["id"])

    signals: list[scoring.CustomerSignal] = []
    replies = []
    rows = await responses.list_responses(session, idea.id)
    reply_mapping = {k: (v, None if v in _LABELLED else "") for k, v in _REPLY_FIELDS.items()}
    for r in rows:
        if not r.classification:
            continue
        customer = _person_key(r.contact_id, r.company_id, r.from_email or r.from_name)
        by_key = first_party.get(r.id, {})
        # Free-text fields score on presence (value ""); labelled ones keep their label.
        signals += _field_signals(
            r.classification,
            reply_mapping,
            by_key,
            customer=customer,
            company=_company_key(r.company_id, None, customer),
            origin="reply",
            source_id=str(r.id),
        )
        replies.append(
            scoring.ReplyInput(
                response_id=str(r.id),
                customer=customer,
                sentiment=str(r.classification.get("sentiment", "neutral")),
                opt_out=r.opt_out,
                evidence_ids=tuple(sorted(by_key.values())),
            )
        )

    interview_inputs = []
    for i in await interviews.list_interviews(session, idea.id):
        customer = _person_key(i.contact_id, i.company_id, i.interviewee_name)
        company = _company_key(i.company_id, i.company_name, customer)
        interview_inputs.append(
            scoring.InterviewInput(
                interview_id=str(i.id),
                customer=customer,
                company=company,
                done=i.status.value == "done",
            )
        )
        signals += _field_signals(
            i.extraction or {},
            _INTERVIEW_FIELDS,
            first_party.get(i.id, {}),
            customer=customer,
            company=company,
            origin="interview",
            source_id=str(i.id),
        )

    counted = {str(e["id"]) for e in evidence}
    wtp_rows = [
        scoring.WtpInput(
            wtp_id=str(w.id),
            customer=_person_key(w.contact_id, w.company_id, w.customer_label),
            stated=w.stated_willingness.value,
            commitment=w.commitment.value,
            evidence_id=str(w.stated_evidence_id)
            if w.stated_evidence_id and str(w.stated_evidence_id) in counted
            else None,
        )
        for w in await wtp.list_signals(session, idea.id)
    ]
    comps = [
        scoring.CompetitorInput(
            competitor_id=str(c["id"]),
            name=c["name"],
            evidence_ids=tuple(sorted(str(x) for x in c["evidence_ids"] if str(x) in counted)),
        )
        for c in await competitors.list_competitors(session, idea.id)
    ]
    open_unknowns = [
        scoring.UnknownInput(str(u.id), u.question, u.priority.value, u.category.value)
        for u in unknowns
        if u.status == UnknownStatus.OPEN
    ]
    has_research = (await analysis.latest_run(session, idea.id)) is not None or bool(
        await research.list_imports(session, idea.id)
    )
    return scoring.ValidationInput(
        has_research=has_research,
        research=tuple(research_items),
        signals=tuple(signals),
        replies=tuple(replies),
        interviews=tuple(interview_inputs),
        wtp=tuple(wtp_rows),
        competitors=tuple(comps),
        open_unknowns=tuple(open_unknowns),
        sent=await outreach.sent_count(session, idea.id),
        replied_messages=len({r.message_id for r in rows if r.message_id}),
    )


async def latest(session: AsyncSession, idea_id: uuid.UUID) -> ValidationScore | None:
    return await session.scalar(
        select(ValidationScore)
        .where(ValidationScore.idea_id == idea_id)
        .order_by(ValidationScore.created_at.desc())
        .limit(1)
    )


async def history(session: AsyncSession, idea_id: uuid.UUID) -> list[ValidationScore]:
    return list(
        await session.scalars(
            select(ValidationScore)
            .where(ValidationScore.idea_id == idea_id)
            .order_by(ValidationScore.created_at.desc())
        )
    )


async def get_score(
    session: AsyncSession, idea_id: uuid.UUID, score_id: uuid.UUID
) -> ValidationScore | None:
    row = await session.get(ValidationScore, score_id)
    return row if row is not None and row.idea_id == idea_id else None


async def current_hash(session: AsyncSession, idea: Idea) -> str:
    return scoring.evaluate(await build_input(session, idea)).inputs_hash


async def recompute(session: AsyncSession, idea: Idea) -> ValidationScore:
    """Score the stored data, keep a snapshot and move the idea to the resulting state."""
    inp = await build_input(session, idea)
    ev = scoring.evaluate(inp)
    data = ev.as_dict()
    row = ValidationScore(
        idea_id=idea.id,
        total=ev.total,
        dimensions=data["dimensions"],
        state=ValidationState(ev.state),
        recommendation=ev.decision.recommendation,
        decision=data["decision"],
        metrics=ev.metrics,
        facts=ev.facts,
        inputs=scoring.canonical(inp),
        inputs_hash=ev.inputs_hash,
        scoring_version=ev.scoring_version,
    )
    session.add(row)
    idea.state = row.state
    await session.commit()
    await session.refresh(row)
    return row
