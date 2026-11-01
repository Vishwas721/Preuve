"""Research imports, fetched sources, verified evidence and per-unknown findings (Phase 1B)."""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.research.pack import EvidenceKind, FindingStatus, Relevance, SourceType, Stance


def _enum(cls: type[enum.Enum]) -> Enum:
    return Enum(cls, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e])


class ImportStatus(enum.StrEnum):
    QUEUED = "queued"
    VERIFYING = "verifying"
    DONE = "done"
    FAILED = "failed"


class FetchStatus(enum.StrEnum):
    OK = "ok"
    FAILED = "failed"  # robots.txt, HTTP error, unsupported type, network


class Verification(enum.StrEnum):
    VERIFIED = "verified"  # quote found on the fetched page
    UNVERIFIABLE = "unverifiable"  # page couldn't be fetched; kept but flagged


class ResearchImport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "research_imports"

    idea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ideas.id", ondelete="CASCADE"), index=True
    )
    schema_version: Mapped[str] = mapped_column(String(20))
    method_version: Mapped[str] = mapped_column(String(20))
    researcher: Mapped[str] = mapped_column(String(50))
    pack: Mapped[dict] = mapped_column(JSON)
    status: Mapped[ImportStatus] = mapped_column(_enum(ImportStatus), default=ImportStatus.QUEUED)
    # counts, rejected items, dropped claims, notes — see service.verify_import
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One fetched URL per idea. Re-imports refresh it."""

    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("idea_id", "url"),)

    idea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ideas.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(Text)
    final_url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fetch_status: Mapped[FetchStatus] = mapped_column(_enum(FetchStatus))
    fetch_note: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    text: Mapped[str | None] = mapped_column(Text)
    full_text: Mapped[str | None] = mapped_column(Text)


class Evidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evidence"
    __table_args__ = (UniqueConstraint("idea_id", "source_id", "quote_key"),)

    idea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ideas.id", ondelete="CASCADE"), index=True
    )
    import_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_imports.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    ref: Mapped[str] = mapped_column(String(32))  # ref within its pack
    quote: Mapped[str] = mapped_column(Text)
    quote_key: Mapped[str] = mapped_column(Text)  # normalized, for dedup
    statement: Mapped[str] = mapped_column(Text)
    source_type: Mapped[SourceType] = mapped_column(_enum(SourceType))
    kind: Mapped[EvidenceKind] = mapped_column(_enum(EvidenceKind))
    stance: Mapped[Stance] = mapped_column(_enum(Stance))
    relevance: Mapped[Relevance] = mapped_column(_enum(Relevance))
    company_name: Mapped[str | None] = mapped_column(String(200))
    published_at: Mapped[date | None] = mapped_column(Date)
    verification: Mapped[Verification] = mapped_column(_enum(Verification))
    verification_note: Mapped[str | None] = mapped_column(Text)
    dismissed: Mapped[bool] = mapped_column(default=False)
    user_edited: Mapped[bool] = mapped_column(default=False)
    original_labels: Mapped[dict | None] = mapped_column(JSON)  # set on first user edit


class EvidenceUnknown(Base):
    __tablename__ = "evidence_unknowns"

    evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True
    )
    unknown_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("unknowns.id", ondelete="CASCADE"), primary_key=True
    )


class UnknownFinding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """What one import concluded about one unknown. The latest per unknown is current."""

    __tablename__ = "unknown_findings"

    unknown_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("unknowns.id", ondelete="CASCADE"), index=True
    )
    import_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_imports.id", ondelete="CASCADE")
    )
    status: Mapped[FindingStatus] = mapped_column(_enum(FindingStatus))
    # list of Claim dicts; evidence_ids are Evidence UUIDs (strings)
    summary: Mapped[list[dict]] = mapped_column(JSON, default=list)
