"""The research pack: the contract between the `/research-idea` skill and Preuve (ADR 0004).

These models are the source of truth. `docs/research-pack.schema.json` is exported from them
(`uv run python -m app.scripts.export_pack_schema`) and a test keeps the export in sync.
"""

import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator, model_validator

from app.llm.guardrails import Claim
from app.modules.analysis.models import Priority, UnknownCategory
from app.modules.analysis.schemas import HypothesisFields

SCHEMA_VERSION = "1.1"  # 1.1 adds competitors + current_solutions (Phase 1C); 1.0 still accepted

MIN_QUOTE_CHARS = 20
MAX_QUOTE_CHARS = 600


class SourceType(StrEnum):
    JOB_POSTING = "job_posting"
    FORUM = "forum"
    REVIEW = "review"
    NEWS = "news"
    INDUSTRY_PUBLICATION = "industry_publication"
    COMPANY_SITE = "company_site"
    REPORT = "report"
    DIRECTORY = "directory"
    OTHER = "other"


class EvidenceKind(StrEnum):
    """Assumptions are not evidence, so they can't appear here."""

    FACT = "fact"  # directly stated by the source
    INFERENCE = "inference"  # a reasonable conclusion from what the source states


class Stance(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"


class Relevance(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CompetitorKind(StrEnum):
    DIRECT = "direct"  # products solving the same problem
    INDIRECT = "indirect"  # different software solving part of it
    MANUAL = "manual"  # spreadsheets, email, paper, chat apps, internal tools
    SERVICE = "service"  # consultants, agencies, freelancers, outsourced providers


class FindingStatus(StrEnum):
    ANSWERED = "answered"
    PARTIALLY_ANSWERED = "partially_answered"
    NO_EVIDENCE_FOUND = "no_evidence_found"


class PackMeta(BaseModel):
    schema_version: Literal["1.0", "1.1"] = SCHEMA_VERSION
    method_version: str = Field(min_length=1, max_length=20, examples=["1"])
    idea_id: uuid.UUID
    researcher: str = Field(default="claude-code", max_length=50)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    queries: list[str] = Field(default_factory=list, description="Searches run, for transparency.")
    notes: str | None = None


class PackEvidence(BaseModel):
    ref: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,31}$", examples=["ev-01"])
    url: str
    title: str = Field(min_length=1, max_length=500)
    source_type: SourceType
    published_at: date | None = None
    quote: str = Field(
        min_length=MIN_QUOTE_CHARS,
        max_length=MAX_QUOTE_CHARS,
        description="Copied verbatim from the page. '…' may join fragments that appear in order.",
    )
    statement: str = Field(min_length=1, max_length=500, description="What the quote shows.")
    kind: EvidenceKind
    stance: Stance
    relevance: Relevance
    unknown_ids: list[uuid.UUID] = Field(default_factory=list)
    company_name: str | None = Field(default=None, max_length=200)

    @field_validator("url")
    @classmethod
    def _http_url(cls, v: str) -> str:
        parts = urlsplit(v)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError("must be an http(s) URL")
        return v


class UnknownFinding(BaseModel):
    unknown_id: uuid.UUID
    status: FindingStatus
    summary: list[Claim] = Field(
        default_factory=list, description="Claims citing evidence refs in `evidence_ids`."
    )


class HypothesisUpdate(HypothesisFields):
    rationale: list[Claim] = Field(min_length=1, description="Why, citing evidence refs.")


class NewUnknown(BaseModel):
    question: str = Field(min_length=1)
    category: UnknownCategory = UnknownCategory.OTHER
    priority: Priority = Priority.MEDIUM


class PackCompetitor(BaseModel):
    ref: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,31}$", examples=["comp-01"])
    name: str = Field(min_length=1, max_length=200)
    url: str | None = Field(
        default=None, description="Product/provider homepage; null for generic workarounds."
    )
    kind: CompetitorKind
    description: str = Field(
        min_length=1, max_length=1000, description="What it covers of the problem."
    )
    pricing_note: str | None = Field(
        default=None,
        max_length=300,
        description="Only if publicly stated; cite it in evidence_refs.",
    )
    evidence_refs: list[str] = Field(min_length=1, description="Evidence refs that mention it.")
    sentiment: list[Claim] = Field(
        default_factory=list, description="What customers praise or complain about, citing refs."
    )

    @field_validator("url")
    @classmethod
    def _http_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        parts = urlsplit(v)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError("must be an http(s) URL")
        return v


class ResearchPack(BaseModel):
    meta: PackMeta
    evidence: list[PackEvidence] = Field(default_factory=list, max_length=200)
    competitors: list[PackCompetitor] = Field(default_factory=list, max_length=50)
    current_solutions: list[Claim] = Field(
        default_factory=list, description="How the problem is solved today, citing evidence refs."
    )
    unknown_findings: list[UnknownFinding] = Field(default_factory=list)
    hypothesis_update: HypothesisUpdate | None = None
    new_unknowns: list[NewUnknown] = Field(default_factory=list, max_length=20)

    def claims(self) -> list[Claim]:
        out = [c for f in self.unknown_findings for c in f.summary]
        if self.hypothesis_update:
            out += self.hypothesis_update.rationale
        out += [c for comp in self.competitors for c in comp.sentiment]
        return out + list(self.current_solutions)

    @model_validator(mode="after")
    def _consistent(self) -> "ResearchPack":
        errors: list[str] = []
        refs = [e.ref for e in self.evidence]
        dupes = sorted({r for r in refs if refs.count(r) > 1})
        if dupes:
            errors.append(f"duplicate evidence refs: {dupes}")
        known = set(refs)
        unknown_refs = sorted({r for c in self.claims() for r in c.evidence_ids if r not in known})
        if unknown_refs:
            errors.append(f"claims cite refs that are not in `evidence`: {unknown_refs}")
        finding_ids = [str(f.unknown_id) for f in self.unknown_findings]
        dupe_findings = sorted({u for u in finding_ids if finding_ids.count(u) > 1})
        if dupe_findings:
            errors.append(f"more than one finding for unknowns: {dupe_findings}")
        comp_refs = [c.ref for c in self.competitors]
        dupe_comps = sorted({r for r in comp_refs if comp_refs.count(r) > 1})
        if dupe_comps:
            errors.append(f"duplicate competitor refs: {dupe_comps}")
        names = [" ".join(c.name.lower().split()) for c in self.competitors]
        dupe_names = sorted({n for n in names if names.count(n) > 1})
        if dupe_names:
            errors.append(f"duplicate competitor names: {dupe_names}")
        bad_comp_refs = sorted(
            {r for c in self.competitors for r in c.evidence_refs if r not in known}
        )
        if bad_comp_refs:
            errors.append(f"competitors cite refs that are not in `evidence`: {bad_comp_refs}")
        for f in self.unknown_findings:
            if f.status != FindingStatus.NO_EVIDENCE_FOUND and not f.summary:
                errors.append(f"finding for {f.unknown_id} is '{f.status}' but has no summary")
        if errors:
            raise ValueError("; ".join(errors))
        return self
