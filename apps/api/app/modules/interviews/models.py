"""Customer interviews (PRD §21–§22): a guide built from open unknowns, notes, and an extraction."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


def _enum(cls: type[enum.Enum]) -> Enum:
    return Enum(cls, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e])


class InterviewStatus(enum.StrEnum):
    PLANNED = "planned"
    DONE = "done"
    CANCELLED = "cancelled"


class JobState(enum.StrEnum):
    """State of the guide or extraction job."""

    NONE = "none"
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class NoteKind(enum.StrEnum):
    LIVE = "live"  # taken during the call
    POST = "post"  # written up afterwards


class Interview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "interviews"

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
    interviewee_name: Mapped[str] = mapped_column(String(200))
    interviewee_role: Mapped[str] = mapped_column(String(200), default="")
    company_name: Mapped[str] = mapped_column(String(200), default="")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[InterviewStatus] = mapped_column(
        _enum(InterviewStatus), default=InterviewStatus.PLANNED
    )
    scheduling_note: Mapped[str] = mapped_column(Text, default="")
    # {"known": [Claim], "questions": [{unknown_id, question, follow_ups, flags}]}
    guide: Mapped[dict | None] = mapped_column(JSON)
    guide_state: Mapped[JobState] = mapped_column(_enum(JobState), default=JobState.NONE)
    # Conversation fields with verbatim quotes, plus proposed answered unknowns.
    extraction: Mapped[dict | None] = mapped_column(JSON)
    extraction_state: Mapped[JobState] = mapped_column(_enum(JobState), default=JobState.NONE)
    dropped: Mapped[list[dict]] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text)


class InterviewNote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "interview_notes"

    interview_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interviews.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[NoteKind] = mapped_column(_enum(NoteKind), default=NoteKind.LIVE)
    text: Mapped[str] = mapped_column(Text)
