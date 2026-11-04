"""Willingness to pay (PRD §23). Stated willingness and commitment are separate on purpose:
the AI may propose a stated willingness from a verified quote, never a commitment."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.prospects import service as prospects
from app.modules.wtp.models import Commitment, StatedWillingness, WtpSignal, WtpSource
from app.modules.wtp.schemas import WtpCreate, WtpUpdate


class WtpError(Exception):
    pass


async def list_signals(session: AsyncSession, idea_id: uuid.UUID) -> list[WtpSignal]:
    return list(
        await session.scalars(
            select(WtpSignal).where(WtpSignal.idea_id == idea_id).order_by(WtpSignal.created_at)
        )
    )


async def get_signal(
    session: AsyncSession, idea_id: uuid.UUID, signal_id: uuid.UUID
) -> WtpSignal | None:
    return await session.scalar(
        select(WtpSignal).where(WtpSignal.id == signal_id, WtpSignal.idea_id == idea_id)
    )


def _check_commitment(commitment: Commitment, committed_at: datetime | None) -> datetime | None:
    if commitment == Commitment.NONE:
        return None
    return committed_at or datetime.now(UTC)


async def create(session: AsyncSession, idea_id: uuid.UUID, data: WtpCreate) -> WtpSignal:
    """Recorded by the user."""
    company_id = None
    if data.contact_id is not None:
        found = await prospects.get_contact(session, idea_id, data.contact_id)
        if found is None:
            raise WtpError("Contact not found on this idea")
        company_id = found[1].id
    fields = data.model_dump()
    fields["committed_at"] = _check_commitment(data.commitment, data.committed_at)
    row = WtpSignal(idea_id=idea_id, company_id=company_id, source=WtpSource.USER, **fields)
    session.add(row)
    await session.commit()
    return row


async def update(session: AsyncSession, row: WtpSignal, data: WtpUpdate) -> WtpSignal:
    """User edits; this is the only way a commitment above `none` is ever recorded."""
    changes = data.model_dump(exclude_unset=True)
    for k, v in changes.items():
        if v is not None or k == "committed_at":
            setattr(row, k, v)
    if "commitment" in changes or "committed_at" in changes:
        row.committed_at = _check_commitment(row.commitment, row.committed_at)
    row.source = WtpSource.USER  # edited by the user: re-analysis must not overwrite it
    await session.commit()
    return row


async def delete_signal(session: AsyncSession, row: WtpSignal) -> None:
    await session.delete(row)
    await session.commit()


async def propose(
    session: AsyncSession,
    *,
    idea_id: uuid.UUID,
    customer_label: str,
    stated: StatedWillingness,
    quote: str,
    evidence_id: uuid.UUID | None,
    contact_id: uuid.UUID | None = None,
    company_id: uuid.UUID | None = None,
    response_id: uuid.UUID | None = None,
    interview_id: uuid.UUID | None = None,
) -> WtpSignal | None:
    """An AI-proposed *stated* willingness from a verified quote (no commitment). One per
    reply/interview: re-analysis replaces it, unless the user has already edited it."""
    if stated == StatedWillingness.UNKNOWN or not quote.strip():
        return None
    owner = (
        WtpSignal.response_id == response_id
        if response_id is not None
        else WtpSignal.interview_id == interview_id
    )
    existing = await session.scalar(select(WtpSignal).where(WtpSignal.idea_id == idea_id, owner))
    if existing is not None and existing.source == WtpSource.USER:
        return existing
    if existing is not None:
        await session.delete(existing)
        await session.flush()
    row = WtpSignal(
        idea_id=idea_id,
        contact_id=contact_id,
        company_id=company_id,
        response_id=response_id,
        interview_id=interview_id,
        customer_label=customer_label,
        stated_willingness=stated,
        stated_quote=quote.strip(),
        stated_evidence_id=evidence_id,
        commitment=Commitment.NONE,  # never set by the AI
        source=WtpSource.AI,
    )
    session.add(row)
    await session.flush()
    return row


async def forget_contact(session: AsyncSession, contact_id: uuid.UUID) -> None:
    """Deletion request (PRD §37): drop this person's WTP records. Does not commit."""
    await session.execute(delete(WtpSignal).where(WtpSignal.contact_id == contact_id))


async def forget_response(session: AsyncSession, response_id: uuid.UUID) -> None:
    """A reply was deleted: drop the AI proposals made from it (user records stay)."""
    await session.execute(
        delete(WtpSignal).where(
            WtpSignal.response_id == response_id, WtpSignal.source == WtpSource.AI
        )
    )


async def forget_interview(session: AsyncSession, interview_id: uuid.UUID) -> None:
    await session.execute(
        delete(WtpSignal).where(
            WtpSignal.interview_id == interview_id, WtpSignal.source == WtpSource.AI
        )
    )
