import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.modules.analysis.models import Source
from app.modules.competitors.models import CompetitorStatus
from app.modules.research.pack import CompetitorKind


@dataclass
class ResearchCompetitorInput:
    """A verified competitor from a research import (refs already resolved to evidence ids)."""

    name: str
    url: str | None
    kind: CompetitorKind
    description: str
    pricing_note: str | None
    evidence_ids: list[uuid.UUID]
    sentiment: list[dict[str, Any]] = field(default_factory=list)


class CompetitorRead(BaseModel):
    id: uuid.UUID
    name: str
    url: str | None
    kind: CompetitorKind
    description: str
    pricing_note: str | None
    sentiment: list[dict[str, Any]]
    source: Source
    status: CompetitorStatus
    user_edited: bool
    evidence_ids: list[uuid.UUID]
    created_at: datetime
    updated_at: datetime


def _check_url(v: str | None) -> str | None:
    if v and not v.startswith(("http://", "https://")):
        raise ValueError("must be an http(s) URL")
    return v or None


class CompetitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: CompetitorKind
    url: str | None = None
    description: str = Field(min_length=1, max_length=1000)
    pricing_note: str | None = Field(default=None, max_length=300)

    _url = field_validator("url")(_check_url)


class CompetitorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: CompetitorKind | None = None
    url: str | None = None
    description: str | None = Field(default=None, min_length=1, max_length=1000)
    pricing_note: str | None = Field(default=None, max_length=300)
    status: CompetitorStatus | None = None

    _url = field_validator("url")(_check_url)
