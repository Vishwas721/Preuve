"""Replies to outreach (PRD §20): pasted or read from the mailbox, classified on the local model.

A reply is private correspondence: minimal fields, deleted with the contact (PRD §37).
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


def _enum(cls: type[enum.Enum]) -> Enum:
    return Enum(cls, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e])


class ResponseChannel(enum.StrEnum):
    PASTE = "paste"
    IMAP = "imap"


class ResponseStatus(enum.StrEnum):
    QUEUED = "queued"
    ANALYZING = "analyzing"
    DONE = "done"
    FAILED = "failed"


class Response(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "responses"

    idea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ideas.id", ondelete="CASCADE"), index=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), index=True
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL")
    )
    from_name: Mapped[str] = mapped_column(String(200), default="")
    from_email: Mapped[str | None] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(Text, default="")
    raw_text: Mapped[str] = mapped_column(Text)  # the reply only, quoted history stripped
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    channel: Mapped[ResponseChannel] = mapped_column(_enum(ResponseChannel))
    # RFC 5322 Message-ID of the reply email: dedupes IMAP polls.
    rfc_message_id: Mapped[str | None] = mapped_column(String(998), unique=True)
    status: Mapped[ResponseStatus] = mapped_column(
        _enum(ResponseStatus), default=ResponseStatus.QUEUED
    )
    opt_out: Mapped[bool] = mapped_column(default=False)
    # Classification fields (see prompts.ResponseClassification), each with its verbatim quote.
    classification: Mapped[dict | None] = mapped_column(JSON)
    # Signals whose quote wasn't found verbatim in the reply: never stored as evidence.
    dropped: Mapped[list[dict]] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
