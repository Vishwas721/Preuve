"""Prospects (PRD §14–§16): companies within an idea, their public contacts and lead scores.

A prospect *is* a company within an idea, so there's no separate prospects table. Contacts are
only people named in a verified quote from a public page (PRD §37: minimal, professional,
deletable).
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


class ProspectStatus(enum.StrEnum):
    NEW = "new"
    SHORTLISTED = "shortlisted"
    EXCLUDED = "excluded"


class Company(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("idea_id", "domain"),)

    idea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ideas.id", ondelete="CASCADE"), index=True
    )
    icp_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("icps.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(200))
    domain: Mapped[str] = mapped_column(String(253))  # research.pack.domain_key(website)
    website: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(200))
    industry: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    size_min: Mapped[int | None] = mapped_column(Integer)
    size_max: Mapped[int | None] = mapped_column(Integer)
    size_signal: Mapped[str | None] = mapped_column(Text)
    size_evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence.id", ondelete="SET NULL")
    )
    in_geo: Mapped[bool | None] = mapped_column()
    geo_evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence.id", ondelete="SET NULL")
    )
    technologies: Mapped[list[str]] = mapped_column(JSON, default=list)
    # {company_fit|technology_fit|other_signals: {rating, rationale, evidence_ids: [uuid str]}}
    assessments: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[ProspectStatus] = mapped_column(
        _enum(ProspectStatus), default=ProspectStatus.NEW
    )
    last_import_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_imports.id", ondelete="SET NULL")
    )


class CompanyEvidence(Base):
    __tablename__ = "company_evidence"

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True
    )


class Contact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("company_id", "name_key"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    name_key: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320))  # only if printed on the source page
    # The verified evidence whose quote names this person; the source of truth for provenance.
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"))
    source_url: Mapped[str] = mapped_column(Text)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LeadScore(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Append-only; the newest row per company is current."""

    __tablename__ = "lead_scores"

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    icp_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("icps.id", ondelete="SET NULL"))
    total: Mapped[int] = mapped_column(Integer)
    components: Mapped[list[dict]] = mapped_column(JSON)
    inputs_hash: Mapped[str] = mapped_column(String(64))
