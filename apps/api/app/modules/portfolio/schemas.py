import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.ideas.models import ValidationState


class EvidenceTally(BaseModel):
    supports: int = 0
    contradicts: int = 0
    neutral: int = 0
    verified: int = 0
    unverifiable: int = 0


class Validation(BaseModel):
    """The latest validation score snapshot (Phase 4); None until one is computed."""

    score: int
    recommendation: str  # build | iterate | investigate | abandon
    headline: str
    validated_conversations: int
    stale: bool  # stored data changed since the snapshot
    computed_at: datetime


class ResearchScore(BaseModel):
    """Phase 6 research score, computed live from verified web evidence."""

    total: int
    band: str  # strong | promising | weak
    version: int


class Funnel(BaseModel):
    """First-party counts, live (PRD §27, §47)."""

    sent: int
    replies: int
    interviews_done: int
    pilot_or_better: int


class PortfolioItem(BaseModel):
    """One idea on the case board (PRD §27/§38)."""

    id: uuid.UUID
    title: str
    target_market: str
    state: ValidationState
    problem: str | None  # current hypothesis problem statement
    evidence: EvidenceTally
    competitors: int
    prospects: int
    top_score: int | None
    unknowns_open: int
    unknowns_answered: int
    busy: bool  # an analysis run or research import is in progress
    validation: Validation | None
    research_score: ResearchScore
    funnel: Funnel
    created_at: datetime
    last_activity: datetime
