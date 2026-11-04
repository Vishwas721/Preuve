import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.experiments.models import ExperimentStatus


class Cohort(BaseModel):
    """Which sent outreach belongs to a cohort. Empty filters match everything."""

    label: str = Field(min_length=1, max_length=100, examples=["Operations directors"])
    campaign_ids: list[uuid.UUID] = Field(default_factory=list)
    icp_id: uuid.UUID | None = None
    role_contains: str = Field(default="", max_length=100, examples=["operations director"])


class CohortResult(BaseModel):
    label: str
    sent: int
    replies: int
    reply_rate: float | None
    positive: int
    problem_confirmed: int
    interview_recommended: int
    interviews_done: int
    small_sample: bool  # fewer than MIN_SAMPLE sent: don't read much into it


class ExperimentResult(BaseModel):
    a: CohortResult
    b: CohortResult | None
    comparison: list[str]  # plain count statements, no interpretation
    computed_at: datetime


class ExperimentCreate(BaseModel):
    hypothesis: str = Field(min_length=1, max_length=2000)
    cohort_a: Cohort
    cohort_b: Cohort | None = None


class ExperimentUpdate(BaseModel):
    hypothesis: str | None = Field(default=None, min_length=1, max_length=2000)
    cohort_a: Cohort | None = None
    cohort_b: Cohort | None = None
    conclusion: str | None = Field(default=None, max_length=4000)
    status: ExperimentStatus | None = None


class ExperimentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    idea_id: uuid.UUID
    hypothesis: str
    cohort_a: Cohort
    cohort_b: Cohort | None
    status: ExperimentStatus
    conclusion: str
    concluded_at: datetime | None
    created_at: datetime
    result: ExperimentResult  # live while running, frozen once concluded
