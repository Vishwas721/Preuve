import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.modules.analysis.models import (
    ICPStatus,
    Priority,
    RunKind,
    RunStatus,
    Source,
    UnknownCategory,
    UnknownStatus,
)
from app.modules.analysis.prompts import ICPRatings
from app.modules.analysis.rubric import WEIGHTS, Criterion

# ---------- runs ----------


class AnalysisRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    idea_id: uuid.UUID
    kind: RunKind
    status: RunStatus
    step: str | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


# ---------- hypothesis ----------


class HypothesisFields(BaseModel):
    problem: str = Field(min_length=1)
    users: str = Field(min_length=1)
    buyer: str = Field(min_length=1)
    decision_maker: str = Field(min_length=1)
    economic_value: str = Field(min_length=1)
    geography: str = Field(min_length=1, max_length=200)
    industry: str = Field(min_length=1, max_length=200)


class HypothesisEdit(HypothesisFields):
    change_note: str | None = Field(default=None, max_length=500)


class HypothesisRead(HypothesisFields):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    source: Source
    change_note: str | None
    created_at: datetime


# ---------- unknowns ----------


class UnknownCreate(BaseModel):
    question: str = Field(min_length=1)
    category: UnknownCategory = UnknownCategory.OTHER
    priority: Priority = Priority.MEDIUM


class UnknownUpdate(BaseModel):
    question: str | None = Field(default=None, min_length=1)
    category: UnknownCategory | None = None
    priority: Priority | None = None
    status: UnknownStatus | None = None


class UnknownRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question: str
    category: UnknownCategory
    priority: Priority
    status: UnknownStatus
    source: Source
    created_at: datetime


# ---------- ICPs ----------


class ICPBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    company_type: str = Field(min_length=1)
    size_min: int | None = Field(default=None, ge=1)
    size_max: int | None = Field(default=None, ge=1)
    geography: str = Field(min_length=1, max_length=200)
    signals: list[str] = Field(default_factory=list)
    user_roles: list[str] = Field(default_factory=list)
    buyer_roles: list[str] = Field(default_factory=list)


class ICPCreate(ICPBase):
    ratings: ICPRatings
    is_primary: bool = False


class ICPUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    company_type: str | None = Field(default=None, min_length=1)
    size_min: int | None = Field(default=None, ge=1)
    size_max: int | None = Field(default=None, ge=1)
    geography: str | None = Field(default=None, min_length=1, max_length=200)
    signals: list[str] | None = None
    user_roles: list[str] | None = None
    buyer_roles: list[str] | None = None
    ratings: ICPRatings | None = None
    is_primary: bool | None = None
    status: ICPStatus | None = None


class ScoreComponent(BaseModel):
    criterion: Criterion
    weight: int
    rating: int
    rationale: str
    points: float


class ICPRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    company_type: str
    size_min: int | None
    size_max: int | None
    geography: str
    signals: list[str]
    roles: dict[str, list[str]]
    score_components: dict[str, dict]
    hypothesis_score: int
    source: Source
    is_primary: bool
    status: ICPStatus
    created_at: datetime

    @computed_field
    @property
    def score_breakdown(self) -> list[ScoreComponent]:
        """Per-criterion points, so the UI can explain the score."""
        out = []
        for c in Criterion:
            comp = self.score_components.get(c.value)
            if comp is None:
                continue
            out.append(
                ScoreComponent(
                    criterion=c,
                    weight=WEIGHTS[c],
                    rating=comp["rating"],
                    rationale=comp["rationale"],
                    points=round(WEIGHTS[c] * (comp["rating"] - 1) / 4, 1),
                )
            )
        return out


# ---------- aggregate ----------


class IdeaAnalysisRead(BaseModel):
    """Everything the idea page needs for Phase 1A in one call."""

    hypothesis: HypothesisRead | None
    unknowns: list[UnknownRead]
    icps: list[ICPRead]
    latest_run: AnalysisRunRead | None
