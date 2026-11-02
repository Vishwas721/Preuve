"""How the problem is solved today (PRD §13): competitors and alternatives, tied to evidence."""

import enum
import uuid

from sqlalchemy import JSON, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.analysis.models import Source
from app.modules.research.pack import CompetitorKind


def _enum(cls: type[enum.Enum]) -> Enum:
    return Enum(cls, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e])


class CompetitorStatus(enum.StrEnum):
    ACTIVE = "active"
    DISMISSED = "dismissed"


class Competitor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "competitors"
    __table_args__ = (UniqueConstraint("idea_id", "name_key"),)

    idea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ideas.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    name_key: Mapped[str] = mapped_column(String(200))  # research.pack.name_key(name)
    url: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[CompetitorKind] = mapped_column(_enum(CompetitorKind))
    description: Mapped[str] = mapped_column(Text)
    pricing_note: Mapped[str | None] = mapped_column(Text)
    # list of Claim dicts (evidence_ids are Evidence ids): what customers praise or complain about
    sentiment: Mapped[list[dict]] = mapped_column(JSON, default=list)
    source: Mapped[Source] = mapped_column(_enum(Source))  # research | user
    status: Mapped[CompetitorStatus] = mapped_column(
        _enum(CompetitorStatus), default=CompetitorStatus.ACTIVE
    )
    user_edited: Mapped[bool] = mapped_column(default=False)
    last_import_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_imports.id", ondelete="SET NULL")
    )


class CompetitorEvidence(Base):
    __tablename__ = "competitor_evidence"

    competitor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("competitors.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True
    )
