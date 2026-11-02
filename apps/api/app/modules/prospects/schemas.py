import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.modules.prospects.models import ProspectStatus


@dataclass
class ContactInput:
    """A contact that already passed verification (name in a verified quote, email on page)."""

    name: str
    role: str
    email: str | None
    evidence_id: uuid.UUID
    source_url: str


@dataclass
class ResearchCompanyInput:
    """A verified company from a research import (refs already resolved to evidence ids)."""

    name: str
    website: str
    domain: str
    icp_id: uuid.UUID | None
    location: str | None
    industry: str | None
    description: str
    size_min: int | None
    size_max: int | None
    size_signal: str | None
    size_evidence_id: uuid.UUID | None
    in_geo: bool | None
    geo_evidence_id: uuid.UUID | None
    technologies: list[str]
    assessments: dict[str, dict[str, Any]]
    evidence_ids: list[uuid.UUID]
    contacts: list[ContactInput] = field(default_factory=list)


class ScoreComponentRead(BaseModel):
    key: str
    label: str
    points: float
    max: int
    reason: str
    evidence_ids: list[str]


class ContactRead(BaseModel):
    id: uuid.UUID
    name: str
    role: str
    email: str | None
    evidence_id: uuid.UUID
    source_url: str
    collected_at: datetime


class ProspectSummary(BaseModel):
    id: uuid.UUID
    name: str
    website: str
    domain: str
    location: str | None
    industry: str | None
    status: ProspectStatus
    icp_id: uuid.UUID | None
    score: int | None
    contacts: int
    top_contact_role: str | None


class ProspectDetail(ProspectSummary):
    description: str
    size_min: int | None
    size_max: int | None
    size_signal: str | None
    in_geo: bool | None
    technologies: list[str]
    evidence_ids: list[uuid.UUID]
    contacts_list: list[ContactRead]
    components: list[ScoreComponentRead]
    scored_at: datetime | None
    inputs_hash: str | None


class ProspectUpdate(BaseModel):
    status: ProspectStatus | None = None
    icp_id: uuid.UUID | None = None
