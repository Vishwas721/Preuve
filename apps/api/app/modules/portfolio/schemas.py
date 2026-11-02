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
    created_at: datetime
    last_activity: datetime
