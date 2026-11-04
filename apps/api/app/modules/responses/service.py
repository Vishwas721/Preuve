"""Replies (PRD §20, §43): ingestion, matching, opt-outs, classification and evidence.

Reply text is private: classification runs with `private=True` (local model unless opted in),
unmatched mailbox email is never stored, and replies are deleted with the contact (PRD §37).
"""

import logging
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import LLMError
from app.llm.router import LLMRouter
from app.llm.tasks import TaskType
from app.modules.ideas.models import Idea
from app.modules.outreach import service as outreach
from app.modules.outreach.models import Message, SuppressionReason
from app.modules.prospects import service as prospects
from app.modules.research import firstparty
from app.modules.research import service as research
from app.modules.research.models import EvidenceOrigin
from app.modules.research.pack import Relevance, Stance
from app.modules.responses import prompts, text
from app.modules.responses.models import Response, ResponseChannel, ResponseStatus
from app.modules.responses.schemas import ResponsePaste
from app.modules.wtp import service as wtp
from app.modules.wtp.models import StatedWillingness

logger = logging.getLogger(__name__)


class ResponseError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


# ---------- ingestion ----------


async def _suppress_if_opt_out(session: AsyncSession, response: Response) -> None:
    response.opt_out = text.is_opt_out(response.raw_text)
    if response.opt_out and response.from_email:
        await outreach.add_suppression(
            session,
            response.from_email,
            SuppressionReason.UNSUBSCRIBED,
            message_id=response.message_id,
            note="Opted out in a reply.",
        )


async def create_paste(session: AsyncSession, idea: Idea, data: ResponsePaste) -> Response:
    """A pasted reply (queued for analysis; the caller enqueues the job). Commits."""
    message: Message | None = None
    contact_id, company_id = data.contact_id, None
    if data.message_id is not None:
        message = await outreach.get_message(session, idea.id, data.message_id)
        if message is None:
            raise ResponseError("Outreach message not found on this idea")
        contact_id, company_id = message.contact_id, message.company_id
    elif contact_id is not None:
        found = await prospects.get_contact(session, idea.id, contact_id)
        if found is None:
            raise ResponseError("Contact not found on this idea")
        company_id = found[1].id

    reply = text.strip_quoted(data.text) or data.text.strip()
    from_email = data.from_email or (message.to_email if message else None)
    response = Response(
        idea_id=idea.id,
        message_id=message.id if message else None,
        contact_id=contact_id,
        company_id=company_id,
        from_name=data.from_name or (message.to_name if message else ""),
        from_email=from_email.strip().lower() if from_email else None,
        subject=f"Re: {message.subject}" if message else "",
        raw_text=reply,
        received_at=data.received_at or _now(),
        channel=ResponseChannel.PASTE,
        status=ResponseStatus.QUEUED,
    )
    session.add(response)
    await session.flush()
    await _suppress_if_opt_out(session, response)
    await session.commit()
    return response


async def ingest_email(session: AsyncSession, raw: bytes) -> tuple[str, uuid.UUID | None]:
    """One mailbox email. Returns (outcome, response id): `reply`, `bounce`, `duplicate`,
    `unmatched` or `empty`. Only matched replies are stored. Commits."""
    msg = text.parse(raw)
    rfc_id = str(msg.get("Message-ID", "")).strip() or None

    bounce = text.bounce_report(msg, raw)
    if bounce is not None:
        hit = False
        for m in await outreach.sent_messages(session, bounce.message_ids):
            hit = (
                await outreach.record_bounce(session, m, "Bounce report received by email.") or hit
            )
        return ("bounce" if hit else "unmatched"), None

    if rfc_id and await session.scalar(
        select(Response.id).where(Response.rfc_message_id == rfc_id)
    ):
        return "duplicate", None

    headers = f"{msg.get('In-Reply-To', '')} {msg.get('References', '')}"
    candidates = await outreach.sent_messages(session, text.referenced_ids(headers))
    name, address = text.sender(msg)
    message = candidates[0] if candidates else None
    if message is None and address:
        message = await outreach.latest_sent_to(session, address)
    if message is None:
        return "unmatched", None  # not an outreach reply: never stored (PRD §37)

    reply = text.strip_quoted(text.body_text(msg))
    if not reply:
        return "empty", None
    response = Response(
        idea_id=await outreach.message_idea_id(session, message),
        message_id=message.id,
        contact_id=message.contact_id,
        company_id=message.company_id,
        from_name=name or message.to_name,
        from_email=address,
        subject=str(msg.get("Subject", "")),
        raw_text=reply,
        received_at=text.received_at(msg),
        channel=ResponseChannel.IMAP,
        rfc_message_id=rfc_id,
        status=ResponseStatus.QUEUED,
    )
    session.add(response)
    await session.flush()
    await _suppress_if_opt_out(session, response)
    await session.commit()
    return "reply", response.id


# ---------- analysis ----------

_SIGNALS: list[tuple[str, str]] = [
    ("problem_confirmed", "Problem confirmed"),
    ("pain", "Pain"),
    ("frequency", "Frequency"),
    ("current_solution", "Current solution"),
    ("time_or_cost", "Time or cost"),
    ("severity", "Severity"),
    ("solution_satisfaction", "Satisfaction with current solution"),
    ("interest", "Interest"),
    ("willingness_to_pay", "Willingness to pay"),
]


def _stance(field: str, value: str) -> Stance:
    """How a signal bears on the hypothesis that the problem is real and worth solving."""
    if field == "problem_confirmed":
        return {"yes": Stance.SUPPORTS, "no": Stance.CONTRADICTS}.get(value, Stance.NEUTRAL)
    if field in ("pain", "frequency", "time_or_cost"):
        return Stance.SUPPORTS
    if field == "severity":
        return {"high": Stance.SUPPORTS, "medium": Stance.SUPPORTS, "low": Stance.CONTRADICTS}.get(
            value, Stance.NEUTRAL
        )
    if field == "solution_satisfaction":  # happy with today's tools = less room for us
        return {"high": Stance.CONTRADICTS, "low": Stance.SUPPORTS}.get(value, Stance.NEUTRAL)
    if field == "willingness_to_pay":
        return {
            "strong": Stance.SUPPORTS,
            "some": Stance.SUPPORTS,
            "none": Stance.CONTRADICTS,
        }.get(value, Stance.NEUTRAL)
    return Stance.NEUTRAL


# Free-text fields whose value may itself be the customer's words (labels like "yes" never are).
_FREE_TEXT = ("pain", "frequency", "current_solution", "time_or_cost")


def recover_quotes(c: prompts.ResponseClassification, reply: str) -> None:
    """Fill an empty quote from a value that appears verbatim in the reply (local models often
    put the customer's words in `value`). Still verified by the matcher before it's stored."""
    for field, _ in _SIGNALS:
        item = getattr(c, field)
        if field in _FREE_TEXT:
            item.quote = firstparty.recover_quote(item.value, item.quote, reply)
        else:  # labels ("yes", "high") are never the customer's words
            item.quote = firstparty.clean_quote(item.quote)


def signals(c: prompts.ResponseClassification, who: str) -> list[firstparty.Signal]:
    out: list[firstparty.Signal] = []
    for field, label in _SIGNALS:
        item = getattr(c, field)
        value = str(getattr(item.value, "value", item.value)).strip()
        if not item.quote.strip() or value in ("", "unclear", "unknown"):
            continue
        out.append(
            firstparty.Signal(
                label=f"{who}: {label.lower()}: {value}",
                quote=item.quote,
                stance=_stance(field, value),
                relevance=Relevance.HIGH,
            )
        )
    return out


async def analyze_response(
    session: AsyncSession, llm: LLMRouter, response_id: uuid.UUID
) -> ResponseStatus | None:
    response = await session.get(Response, response_id)
    if response is None:
        return None
    response.status, response.error = ResponseStatus.ANALYZING, None
    await session.commit()

    original = await session.get(Message, response.message_id) if response.message_id else None
    try:
        c = await llm.structured(
            TaskType.CLASSIFY_RESPONSE,
            prompts.build_prompt(response.raw_text, original.subject if original else None),
            prompts.ResponseClassification,
            system=prompts.SYSTEM,
            private=True,
        )
    except LLMError as exc:
        logger.warning("classify_response failed for %s: %s", response_id, exc)
        response.status = ResponseStatus.FAILED
        response.error = f"Couldn't classify this reply ({exc})."
        await session.commit()
        return response.status

    recover_quotes(c, response.raw_text)
    company = (
        await prospects.get_company(session, response.idea_id, response.company_id)
        if response.company_id
        else None
    )
    who = response.from_name or "Prospect"
    evidence_ids, dropped = await firstparty.record(
        session,
        idea_id=response.idea_id,
        origin=EvidenceOrigin.REPLY,
        owner_id=response.id,
        title=f"Reply from {who}" + (f", {company.name}" if company else ""),
        text=response.raw_text,
        at=response.received_at,
        signals=signals(c, who),
        company_name=company.name if company else None,
    )
    if company is not None:
        await prospects.link_company_evidence(session, company.id, evidence_ids)

    # Quotes that didn't verify are blanked in the stored classification, so nothing unverified
    # is ever shown as the customer's words.
    data = c.model_dump(mode="json")
    bad = {d["quote"] for d in dropped}
    for field, _ in _SIGNALS:
        if data[field]["quote"].strip() in bad:
            data[field]["quote"] = ""
    action, reason = text.recommended_action(c, response.opt_out)
    data["recommended_action"] = {"value": action, "reason": reason}

    wtp_q = c.willingness_to_pay
    if wtp_q.quote.strip() and wtp_q.quote.strip() not in bad:
        ev = await research.evidence_for_quote(session, response.idea_id, evidence_ids, wtp_q.quote)
        await wtp.propose(
            session,
            idea_id=response.idea_id,
            customer_label=who + (f", {company.name}" if company else ""),
            stated=StatedWillingness(wtp_q.value.value),
            quote=wtp_q.quote,
            evidence_id=ev,
            contact_id=response.contact_id,
            company_id=response.company_id,
            response_id=response.id,
        )

    response.classification = data
    response.dropped = dropped
    response.status = ResponseStatus.DONE
    response.analyzed_at = _now()
    await session.commit()
    return response.status


async def mark_failed(session: AsyncSession, response_id: uuid.UUID, error: str) -> None:
    response = await session.get(Response, response_id)
    if response is not None and response.status in (
        ResponseStatus.QUEUED,
        ResponseStatus.ANALYZING,
    ):
        response.status, response.error = ResponseStatus.FAILED, error
        await session.commit()


# ---------- reading ----------


async def list_responses(session: AsyncSession, idea_id: uuid.UUID) -> list[Response]:
    return list(
        await session.scalars(
            select(Response)
            .where(Response.idea_id == idea_id)
            .order_by(Response.received_at.desc())
        )
    )


async def get_response(
    session: AsyncSession, idea_id: uuid.UUID, response_id: uuid.UUID
) -> Response | None:
    return await session.scalar(
        select(Response).where(Response.id == response_id, Response.idea_id == idea_id)
    )


async def response_detail(session: AsyncSession, response: Response) -> dict[str, Any]:
    await session.refresh(response)
    data = {c.key: getattr(response, c.key) for c in Response.__table__.columns}
    company = (
        await prospects.get_company(session, response.idea_id, response.company_id)
        if response.company_id
        else None
    )
    data["company_name"] = company.name if company else None
    data["original"] = None
    if response.message_id:
        m = await session.get(Message, response.message_id)
        if m is not None:
            data["original"] = {
                "id": m.id,
                "campaign_id": m.campaign_id,
                "subject": m.subject,
                "sent_at": m.sent_at,
                "status": m.status.value,
                "body": m.body,
            }
    data["evidence_ids"] = await research.evidence_ids_for(
        session, response.idea_id, response_id=response.id
    )
    return data


async def reanalyze(session: AsyncSession, response: Response) -> None:
    if response.status in (ResponseStatus.QUEUED, ResponseStatus.ANALYZING):
        raise ResponseError("This reply is already being analyzed")
    response.status, response.error = ResponseStatus.QUEUED, None
    await session.commit()


async def delete_response(session: AsyncSession, response: Response) -> None:
    """Remove a reply and everything derived from it (evidence, AI-proposed WTP)."""
    await _drop(session, [response])
    await session.commit()


async def _drop(session: AsyncSession, rows: list[Response]) -> None:
    companies = {r.company_id for r in rows if r.company_id}
    for r in rows:
        await firstparty.clear(session, r.idea_id, EvidenceOrigin.REPLY, r.id)
        await wtp.forget_response(session, r.id)
        await session.delete(r)
    await session.flush()
    for cid in companies:
        await prospects.rescore_company_id(session, cid)


async def forget_contact(session: AsyncSession, contact_id: uuid.UUID, addresses: set[str]) -> None:
    """Deletion request (PRD §37): delete this person's replies and derived evidence."""
    query = select(Response).where(Response.contact_id == contact_id)
    if addresses:
        query = select(Response).where(
            (Response.contact_id == contact_id) | (func.lower(Response.from_email).in_(addresses))
        )
    await _drop(session, list(await session.scalars(query)))


# ---------- dashboard (PRD §43), deterministic ----------


def _top(values: list[str], n: int = 5) -> list[dict[str, Any]]:
    counts = Counter(v.strip().lower() for v in values if v and v.strip())
    return [{"value": v, "count": c} for v, c in counts.most_common(n)]


async def dashboard(session: AsyncSession, idea_id: uuid.UUID) -> dict[str, Any]:
    from app.modules.interviews import service as interviews  # lazy: interviews imports us

    rows = await list_responses(session, idea_id)
    done = [r for r in rows if r.classification]
    sent = await outreach.sent_count(session, idea_id)
    replied_messages = {r.message_id for r in rows if r.message_id}

    def label(r: Response, field: str) -> str:
        return str((r.classification or {}).get(field, {}).get("value", ""))

    signals_ = await wtp.list_signals(session, idea_id)
    return {
        "sent": sent,
        "replies": len(rows),
        "reply_rate": round(len(replied_messages) / sent, 3) if sent else None,
        "positive": sum(1 for r in done if r.classification.get("sentiment") == "positive"),
        "neutral": sum(1 for r in done if r.classification.get("sentiment") == "neutral"),
        "negative": sum(1 for r in done if r.classification.get("sentiment") == "negative"),
        "opt_outs": sum(1 for r in rows if r.opt_out),
        "problem_confirmed": sum(1 for r in done if label(r, "problem_confirmed") == "yes"),
        "interview_recommended": sum(
            1 for r in done if label(r, "recommended_action") == "interview"
        ),
        "interviews_done": await interviews.count_done(session, idea_id),
        "pilot_or_better": sum(
            1 for s in signals_ if s.commitment.value in ("pilot", "signed", "paid")
        ),
        "stated_strong": sum(1 for s in signals_ if s.stated_willingness.value == "strong"),
        # Verbatim customer words, most frequent first (exact repeats only; no AI summary).
        "top_pains": [
            {"quote": r.classification["pain"]["quote"], "from": r.from_name, "id": r.id}
            for r in done
            if r.classification.get("pain", {}).get("quote")
        ][:5],
        "frequencies": _top([label(r, "frequency") for r in done]),
        "current_solutions": _top([label(r, "current_solution") for r in done]),
    }
