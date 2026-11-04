"""Outreach (PRD §17–§19, §36, §37).

Every message is a draft until a human approves it; only approved, unchanged messages to
unsuppressed addresses within the limits are ever sent. `send_campaign` re-checks all of it
immediately before each send.
"""

import logging
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.email.base import (
    EmailDisabledError,
    EmailProvider,
    EmailRecipientRefusedError,
    EmailTransientError,
    OutgoingEmail,
)
from app.llm.base import LLMError, LLMOutputError
from app.llm.guardrails import UngroundedClaimError, verify_citations
from app.llm.router import LLMRouter
from app.llm.tasks import TaskType
from app.modules.analysis import service as analysis
from app.modules.analysis.models import ICP
from app.modules.ideas.models import Idea
from app.modules.outreach import prompts, safety
from app.modules.outreach.models import (
    REDACTED,
    CampaignStatus,
    EmailSource,
    Message,
    MessageStatus,
    OutreachCampaign,
    Suppression,
    SuppressionReason,
)
from app.modules.outreach.schemas import CampaignCreate, CampaignUpdate, MessageUpdate
from app.modules.prospects import service as prospects
from app.modules.research import service as research

logger = logging.getLogger(__name__)

MAX_EVIDENCE_IN_PROMPT = 6
DRAFT_ATTEMPTS = 2
# A message still `drafting` after this long is assumed lost (worker crash) and can be redrafted.
STALE_DRAFT_AFTER = timedelta(minutes=10)
SENT_STATES = (MessageStatus.SENT, MessageStatus.BOUNCED)


class OutreachError(Exception):
    """A request the outreach rules don't allow (surfaced as 409/422)."""


def _now() -> datetime:
    return datetime.now(UTC)


def _day_start(now: datetime) -> datetime:
    return now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


# ---------- suppressions ----------


async def get_suppression(session: AsyncSession, email: str) -> Suppression | None:
    return await session.scalar(
        select(Suppression).where(Suppression.email == safety.normalize_email(email))
    )


async def is_suppressed(session: AsyncSession, email: str) -> bool:
    return await get_suppression(session, email) is not None


async def add_suppression(
    session: AsyncSession,
    email: str,
    reason: SuppressionReason,
    *,
    message_id: uuid.UUID | None = None,
    note: str | None = None,
) -> Suppression:
    """Idempotent; an existing entry is kept as is (does not commit)."""
    existing = await get_suppression(session, email)
    if existing is not None:
        return existing
    row = Suppression(
        email=safety.normalize_email(email), reason=reason, message_id=message_id, note=note
    )
    session.add(row)
    await session.flush()
    return row


async def list_suppressions(session: AsyncSession) -> list[Suppression]:
    return list(await session.scalars(select(Suppression).order_by(Suppression.created_at.desc())))


async def delete_suppression(session: AsyncSession, suppression_id: uuid.UUID) -> None:
    row = await session.get(Suppression, suppression_id)
    if row is None:
        raise LookupError("Suppression not found")
    if row.reason != SuppressionReason.MANUAL:
        raise OutreachError(f"A '{row.reason.value}' suppression can't be removed")
    await session.delete(row)
    await session.commit()


# ---------- campaigns ----------


async def _check_icp(session: AsyncSession, idea_id: uuid.UUID, icp_id: uuid.UUID | None) -> None:
    if icp_id is not None:
        icp = await session.get(ICP, icp_id)
        if icp is None or icp.idea_id != idea_id:
            raise OutreachError("ICP not found on this idea")


async def create_campaign(
    session: AsyncSession, idea: Idea, data: CampaignCreate
) -> OutreachCampaign:
    await _check_icp(session, idea.id, data.icp_id)
    campaign = OutreachCampaign(idea_id=idea.id, **data.model_dump())
    session.add(campaign)
    await session.commit()
    return campaign


async def update_campaign(
    session: AsyncSession, campaign: OutreachCampaign, data: CampaignUpdate
) -> OutreachCampaign:
    for k, v in data.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(campaign, k, v)
    await session.commit()
    return campaign


async def get_campaign(
    session: AsyncSession, idea_id: uuid.UUID, campaign_id: uuid.UUID
) -> OutreachCampaign | None:
    return await session.scalar(
        select(OutreachCampaign).where(
            OutreachCampaign.id == campaign_id, OutreachCampaign.idea_id == idea_id
        )
    )


async def list_campaigns(session: AsyncSession, idea_id: uuid.UUID) -> list[OutreachCampaign]:
    return list(
        await session.scalars(
            select(OutreachCampaign)
            .where(OutreachCampaign.idea_id == idea_id)
            .order_by(OutreachCampaign.created_at.desc())
        )
    )


async def campaign_stats(
    session: AsyncSession, campaign_ids: list[uuid.UUID], now: datetime | None = None
) -> dict[uuid.UUID, dict[str, int]]:
    stats: dict[uuid.UUID, dict[str, int]] = {cid: Counter() for cid in campaign_ids}
    if not campaign_ids:
        return {}
    rows = await session.execute(
        select(Message.campaign_id, Message.status, func.count())
        .where(Message.campaign_id.in_(campaign_ids))
        .group_by(Message.campaign_id, Message.status)
    )
    for cid, status, n in rows:
        stats[cid][status.value] = n
    today = _day_start(now or _now())
    for cid, n in await session.execute(
        select(Message.campaign_id, func.count())
        .where(Message.campaign_id.in_(campaign_ids), Message.sent_at >= today)
        .group_by(Message.campaign_id)
    ):
        stats[cid]["sent_today"] = n
    return {cid: dict(c) for cid, c in stats.items()}


async def sent_today(session: AsyncSession, now: datetime | None = None) -> int:
    today = _day_start(now or _now())
    return await session.scalar(select(func.count()).where(Message.sent_at >= today)) or 0


# ---------- recipients ----------


async def list_recipients(session: AsyncSession, idea_id: uuid.UUID) -> list[dict[str, Any]]:
    """Contacts of this idea's prospects, best-scored company first."""
    pairs = await prospects.list_idea_contacts(session, idea_id)
    scores = {p["id"]: p["score"] for p in await prospects.list_prospects(session, idea_id)}
    contact_ids = [c.id for c, _ in pairs]
    campaigns: dict[uuid.UUID, list[uuid.UUID]] = {cid: [] for cid in contact_ids}
    if contact_ids:
        for contact_id, campaign_id in await session.execute(
            select(Message.contact_id, Message.campaign_id).where(
                Message.contact_id.in_(contact_ids)
            )
        ):
            campaigns[contact_id].append(campaign_id)
    suppressed = set(await session.scalars(select(Suppression.email)))
    rows = [
        {
            "contact_id": c.id,
            "name": c.name,
            "role": c.role,
            "email": c.email,
            "company_id": co.id,
            "company_name": co.name,
            "score": scores.get(co.id),
            "prospect_status": co.status.value,
            "suppressed": bool(c.email) and safety.normalize_email(c.email) in suppressed,
            "campaign_ids": campaigns[c.id],
        }
        for c, co in pairs
    ]
    return sorted(rows, key=lambda r: (-(r["score"] or -1), r["company_name"], r["name"]))


# ---------- drafts ----------


async def create_drafts(
    session: AsyncSession, campaign: OutreachCampaign, contact_ids: list[uuid.UUID]
) -> tuple[list[Message], list[dict[str, Any]]]:
    """One `drafting` message per new contact (commits). The caller enqueues the draft job."""
    created: list[Message] = []
    skipped: list[dict[str, Any]] = []
    for contact_id in dict.fromkeys(contact_ids):
        found = await prospects.get_contact(session, campaign.idea_id, contact_id)
        if found is None:
            skipped.append({"contact_id": contact_id, "reason": "Contact not found on this idea"})
            continue
        contact, company = found
        dup = await session.scalar(
            select(Message.id).where(
                Message.campaign_id == campaign.id, Message.contact_id == contact_id
            )
        )
        if dup is not None:
            skipped.append({"contact_id": contact_id, "reason": "Already in this campaign"})
            continue
        if contact.email and await is_suppressed(session, contact.email):
            skipped.append({"contact_id": contact_id, "reason": "Address is suppressed"})
            continue
        message = Message(
            campaign_id=campaign.id,
            contact_id=contact.id,
            company_id=company.id,
            to_name=contact.name,
            to_email=safety.normalize_email(contact.email) if contact.email else None,
            to_email_source=EmailSource.PUBLIC_PAGE if contact.email else None,
            status=MessageStatus.DRAFTING,
        )
        session.add(message)
        created.append(message)
    await session.commit()
    return created, skipped


async def get_message(
    session: AsyncSession, idea_id: uuid.UUID, message_id: uuid.UUID
) -> Message | None:
    return await session.scalar(
        select(Message)
        .join(OutreachCampaign, OutreachCampaign.id == Message.campaign_id)
        .where(Message.id == message_id, OutreachCampaign.idea_id == idea_id)
    )


async def list_messages(session: AsyncSession, campaign_id: uuid.UUID) -> list[Message]:
    return list(
        await session.scalars(
            select(Message).where(Message.campaign_id == campaign_id).order_by(Message.created_at)
        )
    )


async def _company_evidence(
    session: AsyncSession, idea_id: uuid.UUID, company_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Verified, non-dismissed evidence linked to the company, oldest first."""
    ids = set(await prospects.company_evidence_ids(session, company_id))
    if not ids:
        return []
    return [
        e
        for e in await research.list_evidence(session, idea_id)
        if e["id"] in ids and e["verification"].value == "verified"
    ]


async def _draft_context(
    session: AsyncSession, message: Message, settings: Settings
) -> tuple[prompts.DraftContext, dict[str, str]] | None:
    campaign = await session.get(OutreachCampaign, message.campaign_id)
    found = (
        await prospects.get_contact(session, campaign.idea_id, message.contact_id)
        if message.contact_id
        else None
    )
    if found is None:
        return None
    contact, company = found
    hypothesis = await analysis.get_current_hypothesis(session, campaign.idea_id)
    idea = await session.get(Idea, campaign.idea_id)
    evidence = (await _company_evidence(session, campaign.idea_id, company.id))[
        :MAX_EVIDENCE_IN_PROMPT
    ]
    refs = {f"E{i}": str(e["id"]) for i, e in enumerate(evidence, 1)}
    ctx = prompts.DraftContext(
        problem=hypothesis.problem if hypothesis else idea.description,
        purpose=campaign.purpose,
        sender_name=settings.email_from_name or "the founder",
        contact_name=contact.name,
        contact_role=contact.role,
        company_name=company.name,
        company_description=company.description,
        evidence=tuple(
            prompts.EvidenceItem(ref, e["quote"], e["url"])
            for ref, e in zip(refs, evidence, strict=True)
        ),
    )
    return ctx, refs


async def _ask(llm: LLMRouter, ctx: prompts.DraftContext, refs: dict[str, str]) -> dict[str, Any]:
    """One draft with verified citations, or raise LLMError."""
    last: Exception | None = None
    for _ in range(DRAFT_ATTEMPTS):
        draft = await llm.structured(
            TaskType.DRAFT_OUTREACH,
            prompts.build_prompt(ctx),
            prompts.OutreachDraft,
            system=prompts.SYSTEM,
            temperature=0.3,
        )
        try:
            unknown = sorted(set(draft.cited_refs) - set(refs))
            if unknown:
                raise UngroundedClaimError(f"Draft cites unknown evidence refs: {unknown}")
            claims = verify_citations(draft.why_selected, refs)
        except LLMOutputError as exc:
            last = exc
            logger.warning("draft_outreach rejected: %s", exc)
            continue
        return {
            "subject": draft.subject.strip(),
            "body": draft.body.strip(),
            "cited_evidence_ids": [refs[r] for r in dict.fromkeys(draft.cited_refs)],
            "why_selected": [
                c.model_copy(update={"evidence_ids": [refs[r] for r in c.evidence_ids]}).model_dump(
                    mode="json"
                )
                for c in claims
            ],
        }
    raise LLMError(f"Draft failed verification: {last}")


async def generate_draft(
    session: AsyncSession, llm: LLMRouter, message_id: uuid.UUID, settings: Settings
) -> MessageStatus | None:
    """Fill one `drafting` message. On failure it becomes an empty draft with `draft_error`."""
    message = await session.get(Message, message_id)
    if message is None or message.status != MessageStatus.DRAFTING:
        return None
    built = await _draft_context(session, message, settings)
    if built is None:
        message.status, message.draft_error = MessageStatus.DRAFT, "Contact no longer exists."
        await session.commit()
        return message.status
    ctx, refs = built
    try:
        result = await _ask(llm, ctx, refs)
    except LLMError as exc:
        logger.warning("draft_outreach failed for %s: %s", message_id, exc)
        message.status = MessageStatus.DRAFT
        message.draft_error = f"Couldn't generate a draft ({exc}). Write it by hand or redraft."
        await session.commit()
        return message.status

    await session.refresh(message)
    if message.status != MessageStatus.DRAFTING:  # deleted / edited meanwhile
        return message.status
    message.subject = result["subject"]
    message.body = result["body"]
    message.cited_evidence_ids = result["cited_evidence_ids"]
    message.why_selected = result["why_selected"]
    message.checks = safety.draft_checks(message.subject, message.body, message.to_name)
    message.draft_error = None
    message.status = MessageStatus.DRAFT
    await session.commit()
    return message.status


def is_stale_draft(message: Message, now: datetime | None = None) -> bool:
    return (
        message.status == MessageStatus.DRAFTING
        and (now or _now()) - message.updated_at > STALE_DRAFT_AFTER
    )


async def start_redraft(session: AsyncSession, message: Message) -> None:
    ok = message.status in (MessageStatus.DRAFT, MessageStatus.REJECTED) or is_stale_draft(message)
    if not ok:
        raise OutreachError(f"Only drafts can be redrafted (this one is {message.status.value})")
    message.status = MessageStatus.DRAFTING
    message.updated_at = _now()
    message.draft_error = None
    message.user_edited = False
    await session.commit()


async def mark_draft_failed(
    session: AsyncSession, message_ids: list[uuid.UUID], error: str
) -> None:
    for mid in message_ids:
        message = await session.get(Message, mid)
        if message is not None and message.status == MessageStatus.DRAFTING:
            message.status, message.draft_error = MessageStatus.DRAFT, error
    await session.commit()


# ---------- the approval gate ----------


async def update_message(session: AsyncSession, message: Message, data: MessageUpdate) -> Message:
    """Edit a draft. Editing an approved message sends it back to draft (re-approval needed)."""
    if message.status not in (MessageStatus.DRAFT, MessageStatus.APPROVED):
        raise OutreachError(f"A {message.status.value} message can't be edited")
    changes = data.model_dump(exclude_unset=True)
    if "to_email" in changes:
        email = (changes["to_email"] or "").strip()
        if email and not safety.is_valid_email(email):
            raise OutreachError("That doesn't look like an email address")
        new = safety.normalize_email(email) if email else None
        if new != message.to_email:
            message.to_email = new
            message.to_email_source = EmailSource.USER_ENTERED if new else None
    if changes.get("subject") is not None:
        message.subject = changes["subject"].strip()
    if changes.get("body") is not None:
        message.body = changes["body"]
    message.user_edited = True
    message.checks = safety.draft_checks(message.subject, message.body, message.to_name)
    if message.status == MessageStatus.APPROVED:
        message.status = MessageStatus.DRAFT
        message.approved_hash = message.approved_at = None
    await session.commit()
    return message


async def approve(session: AsyncSession, message: Message) -> Message:
    if message.status != MessageStatus.DRAFT:
        raise OutreachError(f"Only drafts can be approved (this one is {message.status.value})")
    if not message.subject.strip() or not message.body.strip():
        raise OutreachError("Write a subject and a message before approving")
    if not message.to_email:
        raise OutreachError("Add the recipient's email address before approving")
    if await is_suppressed(session, message.to_email):
        raise OutreachError("This address is on the suppression list")
    message.status = MessageStatus.APPROVED
    message.approved_hash = safety.approval_hash(message.to_email, message.subject, message.body)
    message.approved_at = _now()
    await session.commit()
    return message


async def reject(session: AsyncSession, message: Message) -> Message:
    if message.status not in (MessageStatus.DRAFT, MessageStatus.APPROVED):
        raise OutreachError(f"A {message.status.value} message can't be rejected")
    message.status = MessageStatus.REJECTED
    message.approved_hash = message.approved_at = None
    message.rejected_at = _now()
    await session.commit()
    return message


async def reopen(session: AsyncSession, message: Message) -> Message:
    if message.status != MessageStatus.REJECTED:
        raise OutreachError("Only rejected messages can be reopened")
    message.status = MessageStatus.DRAFT
    message.rejected_at = None
    await session.commit()
    return message


async def mark_bounced(session: AsyncSession, message: Message, note: str | None = None) -> Message:
    """Record a bounce that arrived later by email; suppresses the address."""
    if message.status != MessageStatus.SENT:
        raise OutreachError("Only sent messages can be marked as bounced")
    message.status = MessageStatus.BOUNCED
    message.bounced_at = _now()
    if message.to_email and not message.redacted_at:
        await add_suppression(
            session, message.to_email, SuppressionReason.BOUNCED, message_id=message.id, note=note
        )
    await session.commit()
    return message


# ---------- lookups for reply ingestion (Phase 3) ----------


async def sent_messages(session: AsyncSession, message_ids: list[uuid.UUID]) -> list[Message]:
    """Sent (or bounced) outreach messages among these ids."""
    if not message_ids:
        return []
    return list(
        await session.scalars(
            select(Message).where(Message.id.in_(message_ids), Message.status.in_(SENT_STATES))
        )
    )


async def latest_sent_to(
    session: AsyncSession, email: str, within_days: int = 60, now: datetime | None = None
) -> Message | None:
    since = (now or _now()) - timedelta(days=within_days)
    return await session.scalar(
        select(Message)
        .where(
            func.lower(Message.to_email) == safety.normalize_email(email),
            Message.status.in_(SENT_STATES),
            Message.sent_at >= since,
        )
        .order_by(Message.sent_at.desc())
        .limit(1)
    )


async def sent_count(session: AsyncSession, idea_id: uuid.UUID) -> int:
    return (
        await session.scalar(
            select(func.count())
            .select_from(Message)
            .join(OutreachCampaign, OutreachCampaign.id == Message.campaign_id)
            .where(OutreachCampaign.idea_id == idea_id, Message.status.in_(SENT_STATES))
        )
        or 0
    )


async def sent_with_campaigns(
    session: AsyncSession, idea_id: uuid.UUID
) -> list[tuple[Message, OutreachCampaign]]:
    """Every sent (or later bounced) message of an idea, with its campaign."""
    rows = await session.execute(
        select(Message, OutreachCampaign)
        .join(OutreachCampaign, OutreachCampaign.id == Message.campaign_id)
        .where(OutreachCampaign.idea_id == idea_id, Message.status.in_(SENT_STATES))
        .order_by(Message.sent_at)
    )
    return [(m, c) for m, c in rows]


async def first_sent_at(session: AsyncSession) -> datetime | None:
    return await session.scalar(select(func.min(Message.sent_at)))


async def message_idea_id(session: AsyncSession, message: Message) -> uuid.UUID:
    campaign = await session.get(OutreachCampaign, message.campaign_id)
    return campaign.idea_id


async def record_bounce(session: AsyncSession, message: Message, note: str) -> bool:
    """A bounce report arrived for a sent message: mark it and suppress (idempotent, commits)."""
    if message.status == MessageStatus.BOUNCED:
        return False
    await mark_bounced(session, message, note)
    return True


# ---------- sending ----------


async def approved_ids(
    session: AsyncSession, campaign_id: uuid.UUID, message_ids: list[uuid.UUID] | None = None
) -> list[uuid.UUID]:
    query = select(Message.id).where(
        Message.campaign_id == campaign_id, Message.status == MessageStatus.APPROVED
    )
    if message_ids is not None:
        query = query.where(Message.id.in_(message_ids))
    return list(await session.scalars(query.order_by(Message.approved_at)))


def _from_domain(address: str) -> str:
    return address.rsplit("@", 1)[-1] if "@" in address else "preuve.local"


def unsubscribe_url(settings: Settings, message_id: uuid.UUID) -> str:
    token = safety.unsubscribe_token(settings.outreach_secret, message_id)
    return f"{settings.public_api_url.rstrip('/')}/unsubscribe/{token}"


def build_email(message: Message, campaign: OutreachCampaign, settings: Settings) -> OutgoingEmail:
    url = unsubscribe_url(settings, message.id)
    footer = safety.footer(
        sender_name=settings.email_from_name,
        purpose=campaign.purpose,
        unsubscribe_url=url,
        postal_address=settings.email_postal_address,
    )
    return OutgoingEmail(
        from_name=settings.email_from_name,
        from_address=settings.email_from_address,
        to_name=message.to_name,
        to_address=message.to_email or "",
        subject=message.subject,
        body=safety.full_body(message.body, footer),
        message_id=f"<{message.id}@{_from_domain(settings.email_from_address)}>",
        headers={
            "List-Unsubscribe": f"<{url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    )


async def _block(session: AsyncSession, message: Message, reason: str) -> None:
    message.status = MessageStatus.BLOCKED
    message.blocked_reason = reason
    message.approved_hash = None
    await session.commit()


async def _recently_contacted(
    session: AsyncSession, message: Message, now: datetime, days: int
) -> bool:
    since = now - timedelta(days=days)
    other = await session.scalar(
        select(Message.id).where(
            Message.id != message.id,
            func.lower(Message.to_email) == safety.normalize_email(message.to_email or ""),
            Message.status.in_(SENT_STATES),
            Message.sent_at >= since,
        )
    )
    return other is not None


async def send_campaign(
    session: AsyncSession,
    provider: EmailProvider,
    campaign_id: uuid.UUID,
    settings: Settings,
    message_ids: list[uuid.UUID] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Send approved messages, re-checking every rule immediately before each send.

    Returns counts plus notes (e.g. why some were deferred). Each message commits on its own.
    """
    report: dict[str, Any] = {
        "sent": 0,
        "bounced": 0,
        "blocked": 0,
        "deferred": 0,
        "failed": 0,
        "notes": [],
    }
    campaign = await session.get(OutreachCampaign, campaign_id)
    if campaign is None:
        report["notes"].append("Campaign not found.")
        return report
    ids = await approved_ids(session, campaign_id, message_ids)
    stop: str | None = None
    if not provider.enabled:
        stop = "Sending is disabled: set SMTP_HOST in .env."
    elif not (settings.email_from_name.strip() and settings.email_from_address.strip()):
        stop = "Set EMAIL_FROM_NAME and EMAIL_FROM_ADDRESS (a real sender identity) in .env."
    elif campaign.status != CampaignStatus.ACTIVE:
        stop = "Campaign is paused."

    for mid in ids:
        if stop:
            report["deferred"] += 1
            continue
        when = now or _now()
        # Row lock: two send jobs can't both send the same message.
        message = await session.scalar(
            select(Message)
            .where(Message.id == mid)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if message is None or message.status != MessageStatus.APPROVED:
            await session.commit()
            continue  # changed since we listed it: not approved any more
        expected = safety.approval_hash(message.to_email or "", message.subject, message.body)
        if not message.to_email or message.approved_hash != expected:
            # Content changed after approval without going back through the gate.
            message.status = MessageStatus.DRAFT
            message.approved_hash = message.approved_at = None
            message.send_error = "Content changed after approval; approve it again."
            await session.commit()
            report["failed"] += 1
            continue
        if await is_suppressed(session, message.to_email):
            await _block(session, message, "Address is on the suppression list.")
            report["blocked"] += 1
            continue
        if await _recently_contacted(session, message, when, settings.outreach_cooldown_days):
            await _block(
                session,
                message,
                f"This address was emailed in the last {settings.outreach_cooldown_days} days.",
            )
            report["blocked"] += 1
            continue
        today = _day_start(when)
        in_campaign = await session.scalar(
            select(func.count()).where(Message.campaign_id == campaign.id, Message.sent_at >= today)
        )
        if in_campaign >= campaign.daily_limit:
            stop = f"Campaign daily limit reached ({campaign.daily_limit})."
        elif await sent_today(session, when) >= settings.outreach_daily_limit:
            stop = f"Global daily limit reached ({settings.outreach_daily_limit})."
        if stop:
            await session.commit()
            report["deferred"] += 1
            continue

        email = build_email(message, campaign, settings)
        try:
            result = await provider.send(email)
        except EmailRecipientRefusedError as exc:
            message.status = MessageStatus.BOUNCED
            message.bounced_at = message.sent_at = when
            message.sent_body = email.body
            message.send_error = str(exc)
            await add_suppression(
                session, message.to_email, SuppressionReason.BOUNCED, message_id=message.id
            )
            await session.commit()
            report["bounced"] += 1
            continue
        except EmailDisabledError as exc:
            message.send_error = str(exc)
            await session.commit()
            stop = str(exc)
            report["deferred"] += 1
            continue
        except EmailTransientError as exc:
            message.send_error = str(exc)
            await session.commit()
            report["failed"] += 1
            continue

        message.status = MessageStatus.SENT
        message.sent_at = when
        message.sent_body = email.body
        message.sent_headers = result.headers
        message.content_hash = safety.content_hash(result.headers, email.body)
        message.provider_message_id = result.provider_message_id
        message.send_error = None
        await session.commit()
        report["sent"] += 1

    if stop:
        report["notes"].append(stop)
    return report


# ---------- unsubscribe ----------


async def unsubscribe(session: AsyncSession, token: str, secret: str) -> bool:
    """Suppress the address a message went to. False if the token is invalid."""
    message_id = safety.parse_unsubscribe_token(secret, token)
    if message_id is None:
        return False
    message = await session.get(Message, message_id)
    if message is None:
        return False
    if message.to_email and not message.redacted_at:
        await add_suppression(
            session, message.to_email, SuppressionReason.UNSUBSCRIBED, message_id=message.id
        )
        await session.commit()
    return True


# ---------- deletion (PRD §37) ----------


async def contact_addresses(
    session: AsyncSession, contact_id: uuid.UUID, contact_email: str | None
) -> set[str]:
    """Every address known for a contact (their email and any address we wrote to)."""
    rows = await session.scalars(select(Message.to_email).where(Message.contact_id == contact_id))
    found = {safety.normalize_email(e) for e in [contact_email, *rows] if e}
    return found


async def forget_contact(
    session: AsyncSession, contact_id: uuid.UUID, contact_email: str | None
) -> None:
    """Before a contact is deleted: suppress every address, drop unsent messages and redact
    sent ones (their hash, dates, status and cited evidence stay). Does not commit."""
    messages = list(await session.scalars(select(Message).where(Message.contact_id == contact_id)))
    addresses = {safety.normalize_email(e) for e in [contact_email] if e}
    addresses |= {safety.normalize_email(m.to_email) for m in messages if m.to_email}
    for address in sorted(addresses):
        await add_suppression(session, address, SuppressionReason.DELETION_REQUEST)

    unsent = [m.id for m in messages if m.status not in SENT_STATES]
    if unsent:
        await session.execute(delete(Message).where(Message.id.in_(unsent)))
    for m in messages:
        if m.status in SENT_STATES:
            m.to_name = m.subject = m.body = REDACTED
            m.to_email = None
            m.sent_body = REDACTED
            m.sent_headers = None
            m.why_selected = []
            m.checks = []
            m.redacted_at = _now()
    await session.flush()


# ---------- reading ----------


async def message_detail(session: AsyncSession, message: Message) -> dict[str, Any]:
    await session.refresh(message)  # commits expire it; updated_at is set by the database
    campaign = await session.get(OutreachCampaign, message.campaign_id)
    data = {c.key: getattr(message, c.key) for c in Message.__table__.columns}
    data["stale"] = is_stale_draft(message)
    data["prospect"] = None
    if message.company_id:
        company = await prospects.get_company(session, campaign.idea_id, message.company_id)
        if company is not None:
            found = (
                await prospects.get_contact(session, campaign.idea_id, message.contact_id)
                if message.contact_id
                else None
            )
            data["prospect"] = {
                "company_id": company.id,
                "name": company.name,
                "domain": company.domain,
                "score": await prospects.latest_score_total(session, company.id),
                "contact_role": found[0].role if found else None,
                "contact_source_url": found[0].source_url if found else None,
            }
    cited = set(message.cited_evidence_ids)
    data["cited_evidence"] = (
        [
            {k: e[k] for k in ("id", "quote", "statement", "url", "fetched_at")}
            | {"verification": e["verification"].value, "stance": e["stance"].value}
            for e in await research.list_evidence(session, campaign.idea_id, include_dismissed=True)
            if str(e["id"]) in cited
        ]
        if cited
        else []
    )
    return data
