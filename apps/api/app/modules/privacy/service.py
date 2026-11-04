"""Data-subject requests and the privacy/provenance check (Phase 5B, PRD §37).

Everything is scoped to one workspace. Reads other modules' tables through their models only for
read-only lookups; deletions go through the owning modules' service functions.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ideas.models import Idea
from app.modules.interviews.models import Interview, InterviewNote
from app.modules.outreach import safety
from app.modules.outreach import service as outreach
from app.modules.outreach.models import Message, Suppression
from app.modules.privacy import tombstones
from app.modules.prospects import service as prospects
from app.modules.prospects.models import Company, Contact
from app.modules.research.matching import normalize
from app.modules.research.models import Evidence, WebSource
from app.modules.research.service import PAGE_TEXT_RETENTION_DAYS
from app.modules.responses import service as responses
from app.modules.responses.models import Response
from app.modules.wtp.models import WtpSignal

STALE_PROSPECT_DAYS = 180
FREE_MAIL = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "live.com",
    "icloud.com",
    "me.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
    "gmx.com",
    "gmx.de",
    "mail.com",
    "yandex.com",
    "zoho.com",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(v: Any) -> Any:
    return v.isoformat() if isinstance(v, datetime) else v


# ---------- find ----------


async def _contacts(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    email: str | None,
    contact_id: uuid.UUID | None,
) -> list[tuple[Contact, Company, Idea]]:
    q = (
        select(Contact, Company, Idea)
        .join(Company, Company.id == Contact.company_id)
        .join(Idea, Idea.id == Company.idea_id)
        .where(Idea.workspace_id == workspace_id)
    )
    if contact_id is not None:
        q = q.where(Contact.id == contact_id)
    else:
        written = select(Message.contact_id).where(func.lower(Message.to_email) == email)
        q = q.where((func.lower(Contact.email) == email) | (Contact.id.in_(written)))
    return [(c, co, i) for c, co, i in await session.execute(q)]


async def find(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    email: str | None = None,
    contact_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Everything this workspace holds about one person, as ORM rows (see `summary`/`export`)."""
    email = safety.normalize_email(email) if email else None
    contacts = await _contacts(session, workspace_id, email=email, contact_id=contact_id)
    cids = [c.id for c, _, _ in contacts]
    addresses = {email} if email else set()
    for c, _, _ in contacts:
        addresses |= await outreach.contact_addresses(session, c.id, c.email)

    messages: dict[uuid.UUID, Message] = {}
    for a in addresses:
        for m, _ in await outreach.messages_to(session, workspace_id, a):
            messages[m.id] = m
    if cids:
        for m in await session.scalars(select(Message).where(Message.contact_id.in_(cids))):
            messages[m.id] = m

    rq = (
        select(Response)
        .join(Idea, Idea.id == Response.idea_id)
        .where(Idea.workspace_id == workspace_id)
    )
    conds = []
    if addresses:
        conds.append(func.lower(Response.from_email).in_(addresses))
    if cids:
        conds.append(Response.contact_id.in_(cids))
    replies = (
        list(await session.scalars(rq.where(conds[0] if len(conds) == 1 else conds[0] | conds[1])))
        if conds
        else []
    )

    interviews = (
        list(await session.scalars(select(Interview).where(Interview.contact_id.in_(cids))))
        if cids
        else []
    )
    wtp = (
        list(await session.scalars(select(WtpSignal).where(WtpSignal.contact_id.in_(cids))))
        if cids
        else []
    )
    suppressions = (
        list(
            await session.scalars(
                select(Suppression).where(
                    Suppression.email.in_(addresses), Suppression.workspace_id == workspace_id
                )
            )
        )
        if addresses
        else []
    )
    elsewhere = bool(addresses) and any(
        [await outreach.blocked_elsewhere(session, a, workspace_id) for a in addresses]
    )
    return {
        "email": email,
        "addresses": sorted(addresses),
        "contacts": contacts,
        "messages": sorted(messages.values(), key=lambda m: m.created_at),
        "replies": replies,
        "interviews": interviews,
        "wtp": wtp,
        "suppressions": suppressions,
        "blocked_elsewhere": elsewhere,
    }


def summary(found: dict[str, Any]) -> dict[str, Any]:
    """Counts and labels for the lookup screen (no message bodies or reply text)."""
    return {
        "email": found["email"],
        "addresses": found["addresses"],
        "contacts": [
            {
                "id": c.id,
                "idea_id": i.id,
                "idea_title": i.title,
                "name": c.name,
                "role": c.role,
                "company": co.name,
                "email": c.email,
                "source_url": c.source_url,
                "collected_at": c.collected_at,
            }
            for c, co, i in found["contacts"]
        ],
        "messages": len(found["messages"]),
        "replies": len(found["replies"]),
        "interviews": len(found["interviews"]),
        "wtp_records": len(found["wtp"]),
        "suppressed": bool(found["suppressions"]) or found["blocked_elsewhere"],
        "nothing_found": not any(
            found[k]
            for k in ("contacts", "messages", "replies", "interviews", "wtp", "suppressions")
        ),
    }


async def export(session: AsyncSession, found: dict[str, Any]) -> dict[str, Any]:
    """The full record for a data-subject access request, as JSON-ready data."""
    notes: dict[uuid.UUID, list[InterviewNote]] = {}
    for iv in found["interviews"]:
        notes[iv.id] = list(
            await session.scalars(
                select(InterviewNote)
                .where(InterviewNote.interview_id == iv.id)
                .order_by(InterviewNote.created_at)
            )
        )
    first_party = []
    owners = [r.id for r in found["replies"]] + [i.id for i in found["interviews"]]
    if owners:
        for e in await session.scalars(
            select(Evidence).where(
                Evidence.response_id.in_(owners) | Evidence.interview_id.in_(owners)
            )
        ):
            first_party.append(
                {"quote": e.quote, "statement": e.statement, "recorded_at": _iso(e.created_at)}
            )
    contact_sources = []
    for c, _, _ in found["contacts"]:
        e = await session.get(Evidence, c.evidence_id)
        src = await session.get(WebSource, e.source_id) if e else None
        contact_sources.append(
            {
                "contact": c.name,
                "quote": e.quote if e else None,
                "url": src.url if src else c.source_url,
                "fetched_at": _iso(src.fetched_at) if src else None,
            }
        )
    return {
        "generated_at": _iso(_now()),
        "about": (
            "Everything this Preuve workspace holds about the person below. Contacts come from "
            "public web pages (source and quote included); messages are emails sent to them; "
            "replies and interview notes are their own words."
        ),
        "addresses": found["addresses"],
        "contacts": [
            {
                "name": c.name,
                "role": c.role,
                "email": c.email,
                "company": co.name,
                "company_website": co.website,
                "case": i.title,
                "source_url": c.source_url,
                "collected_at": _iso(c.collected_at),
            }
            for c, co, i in found["contacts"]
        ],
        "contact_sources": contact_sources,
        "messages": [
            {
                "to": m.to_email,
                "to_name": m.to_name,
                "subject": m.subject,
                "body": m.sent_body or m.body,
                "status": m.status.value,
                "sent_at": _iso(m.sent_at),
                "redacted_at": _iso(m.redacted_at),
            }
            for m in found["messages"]
        ],
        "replies": [
            {
                "from": r.from_email,
                "from_name": r.from_name,
                "received_at": _iso(r.received_at),
                "text": r.raw_text,
                "classification": r.classification,
            }
            for r in found["replies"]
        ],
        "interviews": [
            {
                "interviewee": iv.interviewee_name,
                "role": iv.interviewee_role,
                "company": iv.company_name,
                "scheduled_at": _iso(iv.scheduled_at),
                "status": iv.status.value,
                "notes": [
                    {"kind": n.kind.value, "text": n.text, "at": _iso(n.created_at)}
                    for n in notes[iv.id]
                ],
            }
            for iv in found["interviews"]
        ],
        "willingness_to_pay": [
            {
                "label": w.customer_label,
                "stated": w.stated_willingness.value,
                "quote": w.stated_quote,
                "commitment": w.commitment.value,
                "note": w.commitment_note,
            }
            for w in found["wtp"]
        ],
        "first_party_evidence": first_party,
        "suppressed": bool(found["suppressions"]) or found["blocked_elsewhere"],
    }


# ---------- erase ----------


async def erase(session: AsyncSession, workspace_id: uuid.UUID, email: str) -> dict[str, int]:
    """Erasure by email in this workspace: every matching contact (with everything derived from
    them), replies from the address, messages to it; then suppress and tombstone the address."""
    email = safety.normalize_email(email)
    found = await find(session, workspace_id, email=email)
    for c, _, i in found["contacts"]:
        await prospects.delete_contact(session, i.id, c.id)
    leftover = list(
        await session.scalars(
            select(Response)
            .join(Idea, Idea.id == Response.idea_id)
            .where(Idea.workspace_id == workspace_id, func.lower(Response.from_email) == email)
        )
    )
    for r in leftover:
        await responses.delete_response(session, r)
    messages = 0
    for a in found["addresses"] or [email]:
        messages += await outreach.forget_address(session, workspace_id, a)
    await tombstones.record(
        session, emails=set(found["addresses"]) | {email}, workspace_id=workspace_id
    )
    await session.commit()
    return {
        "contacts": len(found["contacts"]),
        "replies": len(found["replies"]),
        "messages": len(found["messages"]),
        "interviews": len(found["interviews"]),
        "wtp_records": len(found["wtp"]),
    }


# ---------- check ----------


def _finding(
    kind: str, severity: str, message: str, ids: list[Any], **extra: Any
) -> dict[str, Any]:
    return {
        "kind": kind,
        "severity": severity,
        "message": message,
        "ids": [str(i) for i in ids],
        **extra,
    }


async def check(
    session: AsyncSession, workspace_id: uuid.UUID, now: datetime | None = None
) -> list[dict[str, Any]]:
    """Deterministic privacy and provenance check for one workspace. Empty means no issues."""
    now = now or _now()
    out: list[dict[str, Any]] = []
    ideas = select(Idea.id).where(Idea.workspace_id == workspace_id)

    # Provenance: every exhibit has a source URL, a fetch time and a quote.
    bad = list(
        await session.scalars(
            select(Evidence.id)
            .join(WebSource, WebSource.id == Evidence.source_id)
            .where(
                Evidence.idea_id.in_(ideas),
                (func.coalesce(WebSource.url, "") == "")
                | WebSource.fetched_at.is_(None)
                | (func.length(func.trim(Evidence.quote)) == 0),
            )
        )
    )
    if bad:
        out.append(
            _finding(
                "provenance",
                "high",
                f"{len(bad)} exhibits lack a source URL, fetch time or quote.",
                bad,
            )
        )

    # Provenance: every contact is backed by a quote that names them.
    rows = await session.execute(
        select(Contact, Evidence)
        .join(Company, Company.id == Contact.company_id)
        .join(Evidence, Evidence.id == Contact.evidence_id)
        .where(Company.idea_id.in_(ideas))
    )
    unnamed = [
        c.id for c, e in rows if normalize(c.name) not in normalize(e.quote) or not c.source_url
    ]
    if unnamed:
        out.append(
            _finding(
                "provenance",
                "high",
                f"{len(unnamed)} contacts aren't named in their source quote.",
                unnamed,
            )
        )

    # Minimisation: prospects never contacted for a long time.
    contacted = select(Message.contact_id).where(Message.contact_id.is_not(None))
    stale = list(
        await session.execute(
            select(Contact.id, Contact.name, Company.name, Company.idea_id)
            .join(Company, Company.id == Contact.company_id)
            .where(
                Company.idea_id.in_(ideas),
                Contact.collected_at < now - timedelta(days=STALE_PROSPECT_DAYS),
                Contact.id.not_in(contacted),
            )
        )
    )
    if stale:
        out.append(
            _finding(
                "minimisation",
                "medium",
                f"{len(stale)} contacts were collected over {STALE_PROSPECT_DAYS} days ago "
                "and never contacted. Delete them unless you still plan to.",
                [r[0] for r in stale],
                contacts=[
                    {"id": str(r[0]), "name": r[1], "company": r[2], "idea_id": str(r[3])}
                    for r in stale
                ],
            )
        )

    # Minimisation: personal (free-mail) addresses on contacts.
    personal = [
        cid
        for cid, mail in await session.execute(
            select(Contact.id, Contact.email)
            .join(Company, Company.id == Contact.company_id)
            .where(Company.idea_id.in_(ideas), Contact.email.is_not(None))
        )
        if mail.rsplit("@", 1)[-1].lower() in FREE_MAIL
    ]
    if personal:
        out.append(
            _finding(
                "minimisation",
                "medium",
                f"{len(personal)} contacts have a personal (free-mail) address. Preuve should hold "
                "professional contact details only.",
                personal,
            )
        )

    # Retention: research page text past its 30 days (the daily job is behind or not running).
    overdue = (
        await session.scalar(
            select(func.count())
            .select_from(WebSource)
            .where(
                WebSource.idea_id.in_(ideas),
                WebSource.text_purged_at.is_(None),
                WebSource.fetched_at < now - timedelta(days=PAGE_TEXT_RETENTION_DAYS),
                ~WebSource.url.startswith("preuve://"),
            )
        )
        or 0
    )
    if overdue:
        out.append(
            _finding(
                "retention",
                "low",
                f"{overdue} research pages still hold their text after "
                f"{PAGE_TEXT_RETENTION_DAYS} days. Is the worker running? (It drops it daily.)",
                [],
            )
        )
    return out
