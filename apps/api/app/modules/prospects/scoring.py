"""Explainable lead score (PRD §16), computed in code from stored inputs only.

Every component reports points, max, a reason and the evidence ids behind it. Judgement calls
(company fit, technology fit, other signals) come from the researcher's 0–5 assessments, but
they earn points only when backed by stored evidence. No evidence means no points.
"""

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field

# ---------- inputs ----------


@dataclass(frozen=True)
class LinkedEvidence:
    id: str
    verification: str  # verified | unverifiable
    stance: str  # supports | contradicts | neutral


@dataclass(frozen=True)
class AssessmentInput:
    rating: int  # 0–5
    rationale: str
    evidence_ids: tuple[str, ...]  # stored evidence only


@dataclass(frozen=True)
class ICPTarget:
    name: str
    size_min: int | None
    size_max: int | None
    user_roles: tuple[str, ...]
    buyer_roles: tuple[str, ...]


@dataclass(frozen=True)
class ScoringInput:
    company_fit: AssessmentInput | None
    technology_fit: AssessmentInput | None
    other_signals: AssessmentInput | None
    linked_evidence: tuple[LinkedEvidence, ...]
    contact_roles: tuple[str, ...]
    size_min: int | None
    size_max: int | None
    size_signal: str | None
    size_evidence_id: str | None
    in_geo: bool | None
    geo_evidence_id: str | None
    icp: ICPTarget | None


# ---------- output ----------


@dataclass
class Component:
    key: str
    label: str
    points: float
    max: int
    reason: str
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class ScoreResult:
    total: int
    components: list[Component]
    inputs_hash: str


MAX = {
    "company_fit": 20,
    "problem_evidence": 25,
    "role_relevance": 20,
    "company_size": 10,
    "geography": 5,
    "technology_fit": 10,
    "other_signals": 10,
}
assert sum(MAX.values()) == 100

# ---------- role matching ----------

_PHRASES = {
    "vice president": "vp",
    "chief executive officer": "ceo",
    "chief financial officer": "cfo",
    "chief operating officer": "coo",
    "chief technology officer": "cto",
    "chief information officer": "cio",
}
_STOP = {"of", "the", "and", "for", "to", "in", "at", "a", "an", "&", "or"}
# Industry qualifiers in ICP roles ("Construction Project Managers") that titles usually omit.
_QUALIFIERS = {"construction", "building", "general", "contractor", "company", "firm", "site"}


def _tokens(role: str) -> set[str]:
    text = role.lower()
    for phrase, abbr in _PHRASES.items():
        text = text.replace(phrase, abbr)
    words = re.findall(r"[a-z0-9]+", text)
    out = set()
    for w in words:
        if w in _STOP:
            continue
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]  # managers -> manager, operations -> operation
        out.add(w)
    return out


def role_matches(icp_role: str, contact_role: str) -> bool:
    """All significant words of the ICP role appear in the contact's title."""
    wanted = _tokens(icp_role) - _QUALIFIERS
    return bool(wanted) and wanted <= _tokens(contact_role)


# ---------- components ----------


def _assessment(key: str, label: str, a: AssessmentInput | None) -> Component:
    cap = MAX[key]
    if a is None:
        return Component(key, label, 0, cap, "Not assessed.")
    if not a.evidence_ids:
        return Component(
            key, label, 0, cap, f"Rated {a.rating}/5 but no stored evidence backs it: {a.rationale}"
        )
    points = round(cap * a.rating / 5, 1)
    return Component(key, label, points, cap, f"{a.rating}/5: {a.rationale}", list(a.evidence_ids))


def _problem_evidence(linked: tuple[LinkedEvidence, ...]) -> Component:
    supports = [e for e in linked if e.stance == "supports"]
    weight = sum(1.0 if e.verification == "verified" else 0.5 for e in supports)
    if weight >= 2:
        points = 25
    elif weight >= 1:
        points = 15
    elif weight > 0:
        points = 8
    else:
        points = 0
    verified = sum(e.verification == "verified" for e in supports)
    reason = (
        f"{len(supports)} supporting evidence item(s) about this company ({verified} verified)."
        if supports
        else "No evidence that this company has the problem."
    )
    return Component(
        "problem_evidence", "Problem evidence", points, 25, reason, [e.id for e in supports]
    )


def _role_relevance(roles: tuple[str, ...], icp: ICPTarget | None) -> Component:
    cap = MAX["role_relevance"]
    if not roles:
        return Component("role_relevance", "Role relevance", 0, cap, "No contacts found.")
    if icp is not None:
        for role in roles:
            for buyer in icp.buyer_roles:
                if role_matches(buyer, role):
                    return Component(
                        "role_relevance",
                        "Role relevance",
                        20,
                        cap,
                        f"'{role}' matches ICP buyer role '{buyer}'.",
                    )
        for role in roles:
            for user in icp.user_roles:
                if role_matches(user, role):
                    return Component(
                        "role_relevance",
                        "Role relevance",
                        12,
                        cap,
                        f"'{role}' matches ICP user role '{user}'.",
                    )
    return Component(
        "role_relevance",
        "Role relevance",
        5,
        cap,
        f"Contacts found ({', '.join(roles)}) but none match the ICP's buyer or user roles.",
    )


def _size(inp: ScoringInput) -> Component:
    cap = MAX["company_size"]
    ev = [inp.size_evidence_id] if inp.size_evidence_id else []
    if inp.size_min is None and inp.size_max is None:
        return Component("company_size", "Company size", 0, cap, "Size unknown.")
    c_lo, c_hi = inp.size_min or 1, inp.size_max or 10**9
    label = inp.size_signal or "estimate"
    if inp.icp is None or (inp.icp.size_min is None and inp.icp.size_max is None):
        return Component(
            "company_size", "Company size", 5, cap, f"{label}; ICP sets no size band.", ev
        )
    i_lo, i_hi = inp.icp.size_min or 1, inp.icp.size_max or 10**9
    band = f"ICP band {inp.icp.size_min or '?'}–{inp.icp.size_max or '∞'}"
    if i_lo <= c_lo and c_hi <= i_hi:
        return Component("company_size", "Company size", 10, cap, f"{label}; within {band}.", ev)
    if c_lo <= i_hi and i_lo <= c_hi:
        return Component("company_size", "Company size", 5, cap, f"{label}; overlaps {band}.", ev)
    return Component("company_size", "Company size", 0, cap, f"{label}; outside {band}.", ev)


def _geography(inp: ScoringInput) -> Component:
    cap = MAX["geography"]
    if inp.in_geo and inp.geo_evidence_id:
        return Component(
            "geography", "Geography", 5, cap, "In the target geography.", [inp.geo_evidence_id]
        )
    if inp.in_geo is False:
        return Component("geography", "Geography", 0, cap, "Outside the target geography.")
    return Component("geography", "Geography", 0, cap, "Location not evidenced.")


def _hash(inp: ScoringInput) -> str:
    payload = json.dumps(asdict(inp), sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def score(inp: ScoringInput) -> ScoreResult:
    components = [
        _assessment("company_fit", "Company fit", inp.company_fit),
        _problem_evidence(inp.linked_evidence),
        _role_relevance(inp.contact_roles, inp.icp),
        _size(inp),
        _geography(inp),
        _assessment("technology_fit", "Technology fit", inp.technology_fit),
        _assessment("other_signals", "Other signals", inp.other_signals),
    ]
    total = round(sum(c.points for c in components))
    return ScoreResult(total=total, components=components, inputs_hash=_hash(inp))
