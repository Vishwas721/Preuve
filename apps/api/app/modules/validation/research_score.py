"""Research score: ranks ideas on verified public-web evidence alone, before outreach.

A pure function of `ResearchScoreInput`, built by the validation service from stored rows. No LLM.
It never changes an idea's state or the validation score (Phase 4); it only orders the case board.

Rules are documented in docs/phases/phase-6b-research-score-v2.md (v1: phase-6-research-score.md);
keep the two in sync and bump `RESEARCH_SCORE_VERSION` whenever a rule or constant changes.
"""

from dataclasses import asdict, dataclass, field

RESEARCH_SCORE_VERSION = 2  # 2: source-type weights, diminishing returns, open space

# ---------- constants (agreed at Phase 6B kickoff) ----------

COUNTED_RELEVANCE = ("medium", "high")
SOURCE_WEIGHT = {
    "forum": 3,
    "review": 3,
    "job_posting": 3,
    "news": 2,
    "industry_publication": 2,
    "report": 2,
}  # anything else (company_site, directory, other) weighs 1
DEFAULT_WEIGHT = 1
PROBLEM_MAX, PROBLEM_HALF = 25, 15
PAIN_CATEGORIES = ("cost", "urgency", "frequency")
PAIN_MAX, PAIN_HALF = 15, 9
BALANCE_MAX, BALANCE_FULL_AT = 20, 8  # full balance needs >= 8 independent sources
QUESTIONS_MAX = 10
PRIORITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}
FINDING_CREDIT = {"answered": 1.0, "partially_answered": 0.5, "no_evidence_found": 0.0}
OPEN_SPACE_MAX = 15
CROWDING_PENALTY = {"direct": 3, "indirect": 1}  # manual / service alternatives don't crowd
PROSPECT_PER_COMPANY, PROSPECT_COMPANY_MAX = 1, 10
PROSPECT_PER_CONTACT, PROSPECT_CONTACT_MAX = 1, 5
BAND_STRONG, BAND_PROMISING = 60, 40


# ---------- inputs ----------


@dataclass(frozen=True)
class ResearchSource:
    """One research-origin evidence row that isn't dismissed."""

    evidence_id: str
    domain: str
    stance: str  # supports | contradicts | neutral
    relevance: str  # high | medium | low
    verification: str  # verified | unverifiable
    source_type: str = "other"
    unknown_categories: tuple[str, ...] = ()


@dataclass(frozen=True)
class QuestionInput:
    unknown_id: str
    priority: str  # high | medium | low
    finding: str | None  # latest research finding status, None if never researched


@dataclass(frozen=True)
class CompetitorEntry:
    kind: str  # direct | indirect | manual | service
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResearchScoreInput:
    research: tuple[ResearchSource, ...] = ()
    questions: tuple[QuestionInput, ...] = ()
    competitors: tuple[CompetitorEntry, ...] = ()
    companies: int = 0
    contacts: int = 0


# ---------- result ----------


@dataclass
class ResearchDimension:
    key: str
    label: str
    points: int
    max: int
    reason: str
    gaps: list[str] = field(default_factory=list)


@dataclass
class ResearchScoreResult:
    total: int
    band: str  # strong | promising | weak
    dimensions: list[ResearchDimension]
    version: int = RESEARCH_SCORE_VERSION

    def as_dict(self) -> dict:
        return asdict(self)


def _clamp(points: float, cap: int) -> int:
    return max(0, min(cap, round(points)))


def _diminishing(weight: float, cap: int, half: float) -> int:
    """`cap × W / (W + half)`: more evidence always helps a little, and never saturates."""
    return _clamp(cap * weight / (weight + half), cap) if weight > 0 else 0


def _counted(items: tuple[ResearchSource, ...]) -> list[ResearchSource]:
    return [r for r in items if r.verification == "verified" and r.relevance in COUNTED_RELEVANCE]


def _domain_weights(items: list[ResearchSource]) -> dict[str, int]:
    """Each domain counts once, at the weight of its best source type."""
    best: dict[str, int] = {}
    for r in items:
        w = SOURCE_WEIGHT.get(r.source_type, DEFAULT_WEIGHT)
        best[r.domain] = max(best.get(r.domain, 0), w)
    return best


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _first_hand(weights: dict[str, int]) -> int:
    return sum(1 for w in weights.values() if w == 3)


def research_score(inp: ResearchScoreInput) -> ResearchScoreResult:
    counted = _counted(inp.research)
    supporting = [r for r in counted if r.stance == "supports"]
    support_w = _domain_weights(supporting)
    contra = {r.domain for r in counted if r.stance == "contradicts"}
    s, c = len(support_w), len(contra)
    dims: list[ResearchDimension] = []

    # Problem evidence
    problem = _diminishing(sum(support_w.values()), PROBLEM_MAX, PROBLEM_HALF)
    first = _first_hand(support_w)
    dims.append(
        ResearchDimension(
            "problem",
            "Problem evidence",
            problem,
            PROBLEM_MAX,
            f"{_plural(s, 'independent source')} support the problem, {first} of them first-hand "
            "(forums, reviews, job postings).",
            ["Find people describing the problem first-hand: forums, reviews, job postings."]
            if first < 5
            else [],
        )
    )

    # Pain depth
    pain_w = _domain_weights(
        [r for r in supporting if set(r.unknown_categories) & set(PAIN_CATEGORIES)]
    )
    pain = _diminishing(sum(pain_w.values()), PAIN_MAX, PAIN_HALF)
    dims.append(
        ResearchDimension(
            "pain",
            "Pain depth",
            pain,
            PAIN_MAX,
            f"{_plural(len(pain_w), 'source')} showing cost, urgency or frequency, "
            f"{_first_hand(pain_w)} first-hand.",
            ["Find first-hand evidence of what the problem costs or how often it happens."]
            if _first_hand(pain_w) < 3
            else [],
        )
    )

    # Evidence balance
    if s == 0:
        balance = 0
    else:
        balance = _clamp(
            BALANCE_MAX * s / (s + c) * min(1.0, (s + c) / BALANCE_FULL_AT), BALANCE_MAX
        )
    gaps = []
    if c:
        gaps.append(
            f"{_plural(c, 'independent source')} contradict the problem; check whether they apply."
        )
    if s + c < BALANCE_FULL_AT:
        gaps.append(f"Balance counts fully from {BALANCE_FULL_AT} independent sources.")
    dims.append(
        ResearchDimension(
            "balance",
            "Evidence balance",
            balance,
            BALANCE_MAX,
            f"{s} supporting vs {c} contradicting independent sources.",
            gaps,
        )
    )

    # Questions answered
    possible = sum(PRIORITY_WEIGHT.get(q.priority, 1) for q in inp.questions)
    achieved = sum(
        PRIORITY_WEIGHT.get(q.priority, 1) * FINDING_CREDIT.get(q.finding or "", 0.0)
        for q in inp.questions
    )
    questions = _clamp(QUESTIONS_MAX * achieved / possible, QUESTIONS_MAX) if possible else 0
    unanswered = [q for q in inp.questions if (q.finding or "") != "answered"]
    high_open = sum(1 for q in unanswered if q.priority == "high")
    dims.append(
        ResearchDimension(
            "questions",
            "Questions answered",
            questions,
            QUESTIONS_MAX,
            f"{len(inp.questions) - len(unanswered)} of {_plural(len(inp.questions), 'question')} "
            "answered by research, weighted by priority."
            if inp.questions
            else "No open questions recorded yet.",
            (
                [f"{_plural(high_open, 'high-priority question')} not fully answered."]
                if high_open
                else []
            )
            + (["Analyze the idea to generate its open questions."] if not inp.questions else []),
        )
    )

    # Open space: evidenced direct and indirect competitors crowd the wedge
    verified_ids = {r.evidence_id for r in inp.research if r.verification == "verified"}
    evidenced = [c for c in inp.competitors if set(c.evidence_ids) & verified_ids]
    direct = sum(1 for c in evidenced if c.kind == "direct")
    indirect = sum(1 for c in evidenced if c.kind == "indirect")
    crowding = sum(CROWDING_PENALTY.get(c.kind, 0) for c in evidenced)
    open_space = _clamp(OPEN_SPACE_MAX - crowding, OPEN_SPACE_MAX)
    dims.append(
        ResearchDimension(
            "open_space",
            "Open space",
            open_space,
            OPEN_SPACE_MAX,
            f"{_plural(direct, 'direct competitor')} and "
            f"{_plural(indirect, 'indirect competitor')} with verified evidence.",
            ["The wedge is crowded: show what you do that the direct competitors don't."]
            if direct >= 2
            else [],
        )
    )

    # Reachability
    reach = _clamp(
        min(PROSPECT_COMPANY_MAX, PROSPECT_PER_COMPANY * inp.companies)
        + min(PROSPECT_CONTACT_MAX, PROSPECT_PER_CONTACT * inp.contacts),
        PROSPECT_COMPANY_MAX + PROSPECT_CONTACT_MAX,
    )
    reach_gaps = []
    if inp.companies < PROSPECT_COMPANY_MAX:
        more = PROSPECT_COMPANY_MAX - inp.companies
        reach_gaps.append(f"Add {more} more prospect {'company' if more == 1 else 'companies'}.")
    if inp.contacts < PROSPECT_CONTACT_MAX:
        reach_gaps.append("Find named contacts on prospects' own sites.")
    dims.append(
        ResearchDimension(
            "reachability",
            "Reachability",
            reach,
            PROSPECT_COMPANY_MAX + PROSPECT_CONTACT_MAX,
            f"{inp.companies} prospect {'company' if inp.companies == 1 else 'companies'} and "
            f"{_plural(inp.contacts, 'named contact')}.",
            reach_gaps,
        )
    )

    total = sum(d.points for d in dims)
    band = "strong" if total >= BAND_STRONG else "promising" if total >= BAND_PROMISING else "weak"
    return ResearchScoreResult(total=total, band=band, dimensions=dims)
