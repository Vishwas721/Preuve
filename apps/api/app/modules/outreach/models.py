"""Outreach (PRD §17–§19, §36): campaigns, human-approved messages and the suppression list."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


def _enum(cls: type[enum.Enum]) -> Enum:
    return Enum(cls, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e])


class CampaignStatus(enum.StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"


class MessageStatus(enum.StrEnum):
    DRAFTING = "drafting"  # draft job queued / running
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
    BOUNCED = "bounced"
    BLOCKED = "blocked"  # a send-time safety check refused it (suppressed, cooldown)


class EmailSource(enum.StrEnum):
    PUBLIC_PAGE = "public_page"  # printed on the contact's verified source page
    USER_ENTERED = "user_entered"


class SuppressionReason(enum.StrEnum):
    UNSUBSCRIBED = "unsubscribed"
    BOUNCED = "bounced"
    MANUAL = "manual"
    DELETION_REQUEST = "deletion_request"


REDACTED = "[deleted on request]"


class OutreachCampaign(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "outreach_campaigns"

    idea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ideas.id", ondelete="CASCADE"), index=True
    )
    icp_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("icps.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(200))
    purpose: Mapped[str] = mapped_column(Text)  # the research purpose, in plain words
    daily_limit: Mapped[int] = mapped_column(Integer, default=10)
    status: Mapped[CampaignStatus] = mapped_column(
        _enum(CampaignStatus), default=CampaignStatus.ACTIVE
    )


class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("campaign_id", "contact_id"),)

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("outreach_campaigns.id", ondelete="CASCADE"), index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), index=True
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL")
    )
    to_name: Mapped[str] = mapped_column(String(200))
    to_email: Mapped[str | None] = mapped_column(String(320))
    to_email_source: Mapped[EmailSource | None] = mapped_column(_enum(EmailSource))
    subject: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text, default="")
    why_selected: Mapped[str] = mapped_column(Text, default="")
    cited_evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    checks: Mapped[list[str]] = mapped_column(JSON, default=list)  # draft lint warnings
    status: Mapped[MessageStatus] = mapped_column(
        _enum(MessageStatus), default=MessageStatus.DRAFTING, index=True
    )
    draft_error: Mapped[str | None] = mapped_column(Text)
    user_edited: Mapped[bool] = mapped_column(default=False)
    # SHA-256 of (to_email, subject, body) at approval; the send job refuses if it changed.
    approved_hash: Mapped[str | None] = mapped_column(String(64))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Exactly what went out: every header and the full body (incl. footer).
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    sent_headers: Mapped[dict | None] = mapped_column(JSON)
    sent_body: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64))  # of sent headers + body
    provider_message_id: Mapped[str | None] = mapped_column(String(320))
    send_error: Mapped[str | None] = mapped_column(Text)
    blocked_reason: Mapped[str | None] = mapped_column(Text)
    bounced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    redacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Suppression(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Global: a suppressed address is never contacted again, by any campaign or idea."""

    __tablename__ = "suppressions"

    email: Mapped[str] = mapped_column(String(320), unique=True)  # lower-cased
    reason: Mapped[SuppressionReason] = mapped_column(_enum(SuppressionReason))
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL")
    )
    note: Mapped[str | None] = mapped_column(Text)
