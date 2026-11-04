"""Validation score snapshots (PRD §24–§26). Each recompute stores one row; latest is current."""

import uuid

from sqlalchemy import JSON, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.ideas.models import ValidationState


class ValidationScore(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "validation_scores"

    idea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ideas.id", ondelete="CASCADE"), index=True
    )
    total: Mapped[int] = mapped_column(Integer)
    # scoring.Dimension dicts: key, label, points, max, reason, evidence_ids, record_ids, gaps
    dimensions: Mapped[list[dict]] = mapped_column(JSON)
    state: Mapped[ValidationState] = mapped_column(
        Enum(
            ValidationState,
            native_enum=False,
            length=32,
            values_callable=lambda e: [m.value for m in e],
        )
    )
    recommendation: Mapped[str] = mapped_column(String(20))  # build|iterate|investigate|abandon
    decision: Mapped[dict] = mapped_column(JSON)  # headline, why, strong, weak, uncertainty, …
    metrics: Mapped[dict] = mapped_column(JSON)
    facts: Mapped[dict] = mapped_column(JSON)  # the counts the rules used
    inputs: Mapped[dict] = mapped_column(JSON)  # canonical inputs: re-scoring them reproduces this
    inputs_hash: Mapped[str] = mapped_column(String(64))
    scoring_version: Mapped[int] = mapped_column(Integer)
