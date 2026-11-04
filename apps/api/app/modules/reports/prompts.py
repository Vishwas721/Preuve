"""Prompt and checks for `validation_report` (PRD §44).

The model writes only a short summary of a score that code already computed. Each sentence is a
`Claim` citing exhibit refs (E1, E2…). Sentences are kept only if they cite known exhibits and
every number in them already appears in the score record or in a cited quote.
"""

import re
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.llm.guardrails import EVIDENCE_RULES, Claim, ClaimKind

SYSTEM = (
    EVIDENCE_RULES
    + """\
5. You summarise a validation verdict that has ALREADY been decided by fixed rules. Do not change
   it, argue with it, or add a new recommendation.
6. Write at most 5 short sentences. Every sentence cites the exhibit refs (e.g. "E2") it rests on.
7. Use only numbers that appear in the facts or quotes given. Never estimate or round numbers.
8. Do not praise the idea. If the evidence is thin, say so plainly.
9. If nothing can be said with a citation, return an empty list.
"""
)


class ReportSummary(BaseModel):
    claims: list[Claim] = Field(default_factory=list, max_length=8)


@dataclass(frozen=True)
class Exhibit:
    ref: str  # E1…
    origin: str  # research | reply | interview
    stance: str
    quote: str
    statement: str


def build_prompt(
    *,
    title: str,
    headline: str,
    recommendation: str,
    total: int,
    state: str,
    facts: dict[str, int],
    dimensions: list[dict],
    exhibits: list[Exhibit],
) -> str:
    fact_lines = "\n".join(f"- {k.replace('_', ' ')}: {v}" for k, v in facts.items())
    dim_lines = "\n".join(
        f"- {d['label']}: {d['points']}/{d['max']}. {d['reason']}" for d in dimensions
    )
    ex_lines = (
        "\n".join(
            f'{e.ref} [{e.origin}, {e.stance}]: "{e.quote}" ({e.statement})' for e in exhibits
        )
        or "(none)"
    )
    return f"""\
Idea: {title}
Verdict (decided by rules, do not change): {headline} Recommendation: {recommendation}.
Score: {total}/100. State: {state.replace("_", " ")}.

Facts:
{fact_lines}

Score breakdown:
{dim_lines}

Exhibits:
{ex_lines}

Return JSON: {{"claims": [{{"statement": "...", "kind": "fact" | "inference",
"evidence_ids": ["E1"]}}]}}
"""


_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


_REF = re.compile(r"\bE\d+\b")


def numbers(text: str) -> set[str]:
    """Numbers in a text, ignoring exhibit refs like "E2"."""
    return {n.replace(",", ".") for n in _NUMBER.findall(_REF.sub("", text))}


def check_claim(claim: Claim, known_refs: set[str], allowed_numbers: set[str]) -> str | None:
    """Why a summary sentence is rejected, or None if it may be kept."""
    if claim.kind == ClaimKind.ASSUMPTION:
        return "assumption (not evidence)"
    if not claim.evidence_ids:
        return "cites no exhibit"
    unknown = [r for r in claim.evidence_ids if r not in known_refs]
    if unknown:
        return f"cites unknown exhibits {', '.join(unknown)}"
    extra = numbers(claim.statement) - allowed_numbers
    if extra:
        return f"uses numbers not in the score record: {', '.join(sorted(extra))}"
    return None
