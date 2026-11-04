"""Validation reports (PRD §44): Markdown rendered from one score snapshot, plus a cited summary."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ReportStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Report(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reports"

    idea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ideas.id", ondelete="CASCADE"), index=True
    )
    validation_score_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("validation_scores.id", ondelete="CASCADE")
    )
    status: Mapped[ReportStatus] = mapped_column(
        Enum(
            ReportStatus,
            native_enum=False,
            length=16,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=ReportStatus.QUEUED,
    )
    content: Mapped[str] = mapped_column(Text, default="")  # Markdown
    # Kept summary claims: statement, kind, evidence_ids (exhibit refs), evidence_uuids
    summary: Mapped[list[dict]] = mapped_column(JSON, default=list)
    # Summary sentences rejected by the checks, with the reason (shown, never used)
    dropped: Mapped[list[dict]] = mapped_column(JSON, default=list)
    # exhibit ref -> evidence id, as numbered in this report
    exhibits: Mapped[dict] = mapped_column(JSON, default=dict)
    summary_provider: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
