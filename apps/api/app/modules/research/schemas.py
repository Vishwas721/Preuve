import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.modules.research.models import ImportStatus, Verification
from app.modules.research.pack import EvidenceKind, FindingStatus, Relevance, SourceType, Stance


class ResearchImportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    idea_id: uuid.UUID
    schema_version: str
    method_version: str
    researcher: str
    status: ImportStatus
    report: dict[str, Any]
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class EvidenceRead(BaseModel):
    id: uuid.UUID
    import_id: uuid.UUID
    ref: str
    url: str
    final_url: str | None
    title: str | None
    fetched_at: datetime
    quote: str
    statement: str
    source_type: SourceType
    kind: EvidenceKind
    stance: Stance
    relevance: Relevance
    company_name: str | None
    published_at: date | None
    verification: Verification
    verification_note: str | None
    dismissed: bool
    user_edited: bool
    original_labels: dict[str, str] | None
    unknown_ids: list[uuid.UUID]
    created_at: datetime


class EvidenceUpdate(BaseModel):
    dismissed: bool | None = None
    kind: EvidenceKind | None = None
    stance: Stance | None = None
    relevance: Relevance | None = None


class FindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    unknown_id: uuid.UUID
    import_id: uuid.UUID
    status: FindingStatus
    summary: list[dict[str, Any]]  # Claims; evidence_ids are Evidence ids
    created_at: datetime


class IdeaResearchRead(BaseModel):
    """Everything the idea page needs for Phase 1B in one call."""

    evidence: list[EvidenceRead]
    findings: list[FindingRead]
    imports: list[ResearchImportRead]
