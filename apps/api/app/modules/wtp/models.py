"""Willingness to pay (PRD §23). Stated willingness and actual commitment are kept apart:
the AI may propose a stated willingness from a quote, but only the user records a commitment."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


def _enum(cls: type[enum.Enum]) -> Enum:
    return Enum(cls, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e])


class StatedWillingness(enum.StrEnum):
    UNKNOWN = "unknown"  # not discussed
    NONE = "none"  # said they wouldn't pay
    LOW = "low"
    SOME = "some"
    STRONG = "strong"  # e.g. "I'd pay for this"


class Commitment(enum.StrEnum):
    """Ordered weakest to strongest; anything above NONE is set by the user only."""

    NONE = "none"
    VERBAL = "verbal"
    PILOT = "pilot"
    SIGNED = "signed"
    PAID = "paid"


class WtpSource(enum.StrEnum):
    USER = "user"
    AI = "ai"  # proposed from a reply or interview quote


class WtpSignal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "wtp_signals"

    idea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ideas.id", ondelete="CASCADE"), index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), index=True
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL")
    )
    response_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("responses.id", ondelete="SET NULL")
    )
    interview_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("interviews.id", ondelete="SET NULL")
    )
    customer_label: Mapped[str] = mapped_column(String(300))  # e.g. "Dave Gover, Skyline"
    current_spend: Mapped[str] = mapped_column(Text, default="")
    problem_cost: Mapped[str] = mapped_column(Text, default="")
    expected_price: Mapped[str] = mapped_column(Text, default="")
    stated_willingness: Mapped[StatedWillingness] = mapped_column(
        _enum(StatedWillingness), default=StatedWillingness.UNKNOWN
    )
    stated_quote: Mapped[str] = mapped_column(Text, default="")
    stated_evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence.id", ondelete="SET NULL")
    )
    commitment: Mapped[Commitment] = mapped_column(_enum(Commitment), default=Commitment.NONE)
    commitment_note: Mapped[str] = mapped_column(Text, default="")
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[WtpSource] = mapped_column(_enum(WtpSource), default=WtpSource.USER)
