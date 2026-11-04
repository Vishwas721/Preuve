import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.reports.models import ReportStatus


class SummaryClaim(BaseModel):
    statement: str
    kind: str
    evidence_ids: list[str]  # exhibit refs (E1…)
    evidence_uuids: list[str]


class DroppedClaim(BaseModel):
    statement: str
    reason: str


class ReportRead(BaseModel):
    id: uuid.UUID
    idea_id: uuid.UUID
    validation_score_id: uuid.UUID
    status: ReportStatus
    content: str
    summary: list[SummaryClaim]
    dropped: list[DroppedClaim]
    exhibits: dict[str, str]  # evidence id -> exhibit ref
    summary_provider: str | None
    error: str | None
    generated_at: datetime | None
    created_at: datetime
    total: int | None
    recommendation: str | None
