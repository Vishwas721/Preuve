import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.ideas.models import ValidationState


class DimensionRead(BaseModel):
    key: str
    label: str
    points: int
    max: int
    reason: str
    evidence_ids: list[str]
    record_ids: list[str]
    gaps: list[str]


class PointRead(BaseModel):
    text: str
    evidence_ids: list[str]
    record_ids: list[str]


class DecisionRead(BaseModel):
    recommendation: str
    headline: str
    why: str
    strong: list[PointRead]
    weak: list[PointRead]
    uncertainty: str
    next_actions: list[str]


class MetricsRead(BaseModel):
    validated_conversations: int
    response_rate: float | None
    problem_confirmation_rate: float | None
    interview_conversion: float | None
    commercial_validation: float | None


class ScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    idea_id: uuid.UUID
    total: int
    dimensions: list[DimensionRead]
    state: ValidationState
    recommendation: str
    decision: DecisionRead
    metrics: MetricsRead
    facts: dict[str, int]
    inputs_hash: str
    scoring_version: int
    created_at: datetime


class ScoreStatus(BaseModel):
    """The latest snapshot (if any) and whether the stored data changed since it was taken."""

    score: ScoreRead | None
    stale: bool


class ScoreSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    total: int
    state: ValidationState
    recommendation: str
    created_at: datetime
