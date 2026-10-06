"""Evidence guardrails (PRD §12, §35).

AI output is never evidence by itself. Every statement the AI makes is a `Claim` labelled as a
fact, an inference, or an assumption, and facts must cite the evidence records they come from.
"""

from collections.abc import Iterable
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from app.llm.base import LLMOutputError

NO_EVIDENCE_FOUND = "No evidence found."

# Shared system prompt for any task that reasons over sources.
EVIDENCE_RULES = """\
You are a careful market-research analyst. Rules:
1. Use ONLY the sources provided in the prompt. Do not use outside knowledge as evidence.
2. Label every statement:
   - "fact": directly stated in a provided source. Cite its evidence id(s).
   - "inference": a reasonable conclusion drawn from cited sources. Cite them.
   - "assumption": not supported by the sources. No citation needed.
3. Never invent evidence ids, companies, quotes, numbers, or URLs.
4. If the sources don't support anything, return an empty list. Do not fill gaps with
   generic statements like "companies commonly experience...".
"""


class ClaimKind(StrEnum):
    FACT = "fact"
    INFERENCE = "inference"
    ASSUMPTION = "assumption"


class Claim(BaseModel):
    statement: str = Field(min_length=1)
    kind: ClaimKind
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _facts_need_evidence(self) -> "Claim":
        if self.kind == ClaimKind.FACT and not self.evidence_ids:
            raise ValueError("a 'fact' claim must cite at least one evidence id")
        return self


class UngroundedClaimError(LLMOutputError):
    """The model cited evidence ids that don't exist in the sources it was given."""


def verify_citations(claims: Iterable[Claim], known_evidence_ids: Iterable[str]) -> list[Claim]:
    """Reject claims citing unknown evidence ids (i.e. hallucinated citations)."""
    known = set(known_evidence_ids)
    claims = list(claims)
    unknown = sorted({eid for c in claims for eid in c.evidence_ids if eid not in known})
    if unknown:
        raise UngroundedClaimError(f"Claims cite unknown evidence ids: {unknown}")
    return claims
