"""Research score: ranks ideas on verified public-web evidence alone, before outreach.

A pure function of `ResearchScoreInput`, built by the validation service from stored rows. No LLM.
It never changes an idea's state or the validation score (Phase 4); it only orders the case board.

Rules are documented in docs/phases/phase-6-research-score.md; keep the two in sync and bump
`RESEARCH_SCORE_VERSION` whenever a rule or constant changes.
"""

from dataclasses import asdict, dataclass, field

from app.modules.validation.scoring import ResearchItem

RESEARCH_SCORE_VERSION = 1

# ---------- constants (agreed at Phase 6 kickoff) ----------

COUNTED_RELEVANCE = ("medium", "high")
PROBLEM_PER_DOMAIN, PROBLEM_MAX = 3, 30
PAIN_CATEGORIES = ("cost", "urgency", "frequency")
PAIN_PER_DOMAIN, PAIN_MAX = 3, 15
BALANCE_MAX, BALANCE_FULL_AT = 20, 5  # full balance needs >= 5 independent sources
QUESTIONS_MAX = 15
PRIORITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}
FINDING_CREDIT = {"answered": 1.0, "partially_answered": 0.5, "no_evidence_found": 0.0}
ALTERNATIVES_PER_COMPETITOR, ALTERNATIVES_MAX = 1, 5
PROSPECT_PER_COMPANY, PROSPECT_COMPANY_MAX = 1, 10
PROSPECT_PER_CONTACT, PROSPECT_CONTACT_MAX = 1, 5
BAND_STRONG, BAND_PROMISING = 60, 40


# ---------- inputs ----------


@dataclass(frozen=True)
class QuestionInput:
    unknown_id: str
    priority: str  # high | medium | low
    finding: str | None  # latest research finding status, None if never researched


@dataclass(frozen=True)
class ResearchScoreInput:
    research: tuple[ResearchItem, ...] = ()
    questions: tuple[QuestionInput, ...] = ()
    competitor_evidence: tuple[tuple[str, ...], ...] = ()  # per competitor: its evidence ids
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


def _counted(items: tuple[ResearchItem, ...]) -> list[ResearchItem]:
    return [r for r in items if r.verification == "verified" and r.relevance in COUNTED_RELEVANCE]


def _domains(items: list[ResearchItem], stance: str) -> set[str]:
    return {r.domain for r in items if r.stance == stance}


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def research_score(inp: ResearchScoreInput) -> ResearchScoreResult:
    counted = _counted(inp.research)
    support = _domains(counted, "supports")
    contra = _domains(counted, "contradicts")
    s, c = len(support), len(contra)
    dims: list[ResearchDimension] = []

    # Problem evidence
    problem = _clamp(PROBLEM_PER_DOMAIN * s, PROBLEM_MAX)
    dims.append(
        ResearchDimension(
            "problem",
            "Problem evidence",
            problem,
            PROBLEM_MAX,
            f"{_plural(s, 'independent source')} with verified evidence supporting the problem.",
            []
            if problem >= PROBLEM_MAX
            else [
                f"Find {-(-(PROBLEM_MAX - problem) // PROBLEM_PER_DOMAIN)} more independent "
                "sources describing the problem."
            ],
        )
    )

    # Pain depth
    pain_domains = {
        r.domain
        for r in counted
        if r.stance == "supports" and set(r.unknown_categories) & set(PAIN_CATEGORIES)
    }
    pain = _clamp(PAIN_PER_DOMAIN * len(pain_domains), PAIN_MAX)
    dims.append(
        ResearchDimension(
            "pain",
            "Pain depth",
            pain,
            PAIN_MAX,
            f"{_plural(len(pain_domains), 'source')} showing cost, urgency or frequency.",
            []
            if pain >= PAIN_MAX
            else [
                "Find evidence of what the problem costs, how often it happens or how urgent it is."
            ],
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

    # Alternatives mapped
    verified_ids = {r.evidence_id for r in inp.research if r.verification == "verified"}
    mapped = sum(1 for ids in inp.competitor_evidence if set(ids) & verified_ids)
    alternatives = _clamp(ALTERNATIVES_PER_COMPETITOR * mapped, ALTERNATIVES_MAX)
    dims.append(
        ResearchDimension(
            "alternatives",
            "Alternatives mapped",
            alternatives,
            ALTERNATIVES_MAX,
            f"{_plural(mapped, 'alternative')} backed by verified evidence.",
            []
            if alternatives >= ALTERNATIVES_MAX
            else ["Map how the problem is solved today, with sources."],
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
