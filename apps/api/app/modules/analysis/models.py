"""Idea analysis (PRD §9–§10): hypothesis versions, unknowns (the research plan), ICPs, runs.

Everything here is an *assumption* until later phases attach evidence.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


def _enum(cls: type[enum.Enum]) -> Enum:
    return Enum(cls, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e])


class Source(enum.StrEnum):
    AI = "ai"
    USER = "user"
    RESEARCH = "research"  # from an imported research pack (Phase 1B)


class UnknownCategory(enum.StrEnum):
    FREQUENCY = "frequency"
    COST = "cost"
    CURRENT_SOLUTION = "current_solution"
    BUYER = "buyer"
    BUDGET = "budget"
    ALTERNATIVES = "alternatives"
    URGENCY = "urgency"
    OTHER = "other"


class Priority(enum.StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class UnknownStatus(enum.StrEnum):
    OPEN = "open"
    ANSWERED = "answered"
    DROPPED = "dropped"


class ICPStatus(enum.StrEnum):
    ACTIVE = "active"
    DISMISSED = "dismissed"


class RunKind(enum.StrEnum):
    FULL = "full"  # hypothesis + unknowns + ICPs
    ICPS = "icps"  # ICPs only, from the current hypothesis


class RunStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Hypothesis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Append-only: each edit or re-generation is a new version; the highest is current."""

    __tablename__ = "hypotheses"
    __table_args__ = (UniqueConstraint("idea_id", "version"),)

    idea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ideas.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    problem: Mapped[str] = mapped_column(Text)
    users: Mapped[str] = mapped_column(Text)
    buyer: Mapped[str] = mapped_column(Text)
    decision_maker: Mapped[str] = mapped_column(Text)
    economic_value: Mapped[str] = mapped_column(Text)
    geography: Mapped[str] = mapped_column(String(200))
    industry: Mapped[str] = mapped_column(String(200))
    source: Mapped[Source] = mapped_column(_enum(Source))
    change_note: Mapped[str | None] = mapped_column(Text)


class Unknown(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "unknowns"

    idea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ideas.id", ondelete="CASCADE"), index=True
    )
    question: Mapped[str] = mapped_column(Text)
    category: Mapped[UnknownCategory] = mapped_column(_enum(UnknownCategory))
    priority: Mapped[Priority] = mapped_column(_enum(Priority))
    status: Mapped[UnknownStatus] = mapped_column(_enum(UnknownStatus), default=UnknownStatus.OPEN)
    source: Mapped[Source] = mapped_column(_enum(Source))


class ICP(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "icps"

    idea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ideas.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    company_type: Mapped[str] = mapped_column(Text)
    size_min: Mapped[int | None] = mapped_column(Integer)
    size_max: Mapped[int | None] = mapped_column(Integer)
    geography: Mapped[str] = mapped_column(String(200))
    signals: Mapped[list[str]] = mapped_column(JSON, default=list)
    # {"users": [...], "buyers": [...]}
    roles: Mapped[dict[str, list[str]]] = mapped_column(JSON, default=dict)
    # {criterion: {"rating": 1-5, "rationale": str}} — see rubric.py
    score_components: Mapped[dict[str, dict]] = mapped_column(JSON, default=dict)
    hypothesis_score: Mapped[int] = mapped_column(Integer)  # computed from the rubric
    source: Mapped[Source] = mapped_column(_enum(Source))
    is_primary: Mapped[bool] = mapped_column(default=False)
    status: Mapped[ICPStatus] = mapped_column(_enum(ICPStatus), default=ICPStatus.ACTIVE)


class AnalysisRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "analysis_runs"

    idea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ideas.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[RunKind] = mapped_column(_enum(RunKind))
    status: Mapped[RunStatus] = mapped_column(_enum(RunStatus), default=RunStatus.QUEUED)
    step: Mapped[str | None] = mapped_column(String(32))
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
