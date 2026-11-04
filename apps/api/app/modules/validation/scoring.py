"""Validation score, state and decision (PRD §24–§26, §47–§48), computed in code only.

Everything here is a pure function of `ValidationInput`, which the service builds from stored
rows. No LLM is involved, so the same inputs always give the same score, state and advice.

Rules are documented in docs/phases/phase-4-validation-decision.md; keep the two in sync and bump
`SCORING_VERSION` whenever a rule or constant changes.
"""

import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field

SCORING_VERSION = 1

# ---------- constants (agreed at Phase 4 kickoff) ----------

# Problem evidence (20)
PROBLEM_PER_CUSTOMER, PROBLEM_CUSTOMER_MAX = 3, 12
PROBLEM_PER_DOMAIN, PROBLEM_DOMAIN_MAX = 2, 8
PROBLEM_DENIAL_PENALTY, PROBLEM_CONTRA_DOMAIN_PENALTY = 3, 2
# Frequency (10)
FREQ_PER_CUSTOMER, FREQ_CUSTOMER_MAX = 2, 8
FREQ_PER_RESEARCH, FREQ_RESEARCH_MAX = 1, 2
# Severity (15)
SEVERITY_POINTS = {"high": 3, "medium": 1, "low": -2}
SEVERITY_COST_BONUS, SEVERITY_CUSTOMER_MAX = 2, 13
SEVERITY_PER_RESEARCH, SEVERITY_RESEARCH_MAX = 1, 2
# Customer response (15)
RESPONSE_PER_CUSTOMER, RESPONSE_CUSTOMER_MAX = 2, 10
RESPONSE_MIN_SENT = 10
RESPONSE_RATE_HIGH, RESPONSE_RATE_HIGH_POINTS = 0.10, 5
RESPONSE_RATE_LOW, RESPONSE_RATE_LOW_POINTS = 0.05, 2
# Interview confirmation (15)
INTERVIEW_POINTS, INTERVIEW_MAX = 5, 15
# Existing alternatives (10)
ALT_PER_CUSTOMER, ALT_CUSTOMER_MAX = 2, 6
ALT_PER_COMPETITOR, ALT_COMPETITOR_MAX = 1, 4
ALT_SATISFIED_PENALTY = 2
# Willingness to pay (15)
WTP_COMMITMENT_POINTS = {"paid": 15, "signed": 12, "pilot": 8, "verbal": 4}
WTP_STATED_POINTS = {"strong": 3, "some": 2}
WTP_STATED_NONE_PENALTY = 2

# States (PRD §25)
EARLY_CUSTOMERS, EARLY_DOMAINS = 1, 3
PROBLEM_VALIDATED_COMPANIES, PROBLEM_VALIDATED_INTERVIEWS = 3, 1
CONFIRM_TO_DENY_RATIO = 2
SOLUTION_HIGH_INTEREST = 3
COMMERCIAL_PILOTS, COMMERCIAL_PAID = 2, 1
MVP_SCORE, MVP_INTERVIEWS = 70, 5

# Decision (PRD §26)
ABANDON_DENIALS = 3
ITERATE_NO_WTP = 2
ITERATE_SATISFIED = 2
WEAK_SCORE = 40

PILOT_OR_BETTER = ("pilot", "signed", "paid")
LEVEL_ORDER = {"high": 3, "medium": 2, "low": 1}

# ---------- inputs ----------


@dataclass(frozen=True)
class ResearchItem:
    """A verified or unverifiable research evidence row that isn't dismissed."""

    evidence_id: str
    domain: str
    stance: str  # supports | contradicts | neutral
    relevance: str  # high | medium | low
    verification: str  # verified | unverifiable
    unknown_categories: tuple[str, ...] = ()


@dataclass(frozen=True)
class CustomerSignal:
    """One counted first-party evidence row, normalised to a field the score understands.

    field: problem_confirmed (value yes|no), frequency, severity (high|medium|low), cost,
    current_solution, solution_satisfaction (high|medium|low), interest (high|medium|low),
    objection, wtp_stated (strong|some|low|none).
    """

    evidence_id: str
    customer: str  # independent-customer key (contact, else company, else email/name)
    company: str  # independent-company key (company, else company name, else customer)
    origin: str  # reply | interview
    source_id: str  # response id or interview id
    field: str
    value: str = ""


@dataclass(frozen=True)
class ReplyInput:
    response_id: str
    customer: str
    sentiment: str  # positive | neutral | negative
    opt_out: bool
    evidence_ids: tuple[str, ...]  # counted evidence from this reply


@dataclass(frozen=True)
class InterviewInput:
    interview_id: str
    customer: str
    company: str
    done: bool


@dataclass(frozen=True)
class WtpInput:
    wtp_id: str
    customer: str
    stated: str  # unknown | none | low | some | strong
    commitment: str  # none | verbal | pilot | signed | paid
    evidence_id: str | None


@dataclass(frozen=True)
class CompetitorInput:
    competitor_id: str
    name: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class UnknownInput:
    unknown_id: str
    question: str
    priority: str  # high | medium | low
    category: str


@dataclass(frozen=True)
class ValidationInput:
    has_research: bool  # an analysis run or a research import exists
    research: tuple[ResearchItem, ...] = ()
    signals: tuple[CustomerSignal, ...] = ()
    replies: tuple[ReplyInput, ...] = ()
    interviews: tuple[InterviewInput, ...] = ()
    wtp: tuple[WtpInput, ...] = ()
    competitors: tuple[CompetitorInput, ...] = ()
    open_unknowns: tuple[UnknownInput, ...] = ()
    sent: int = 0
    replied_messages: int = 0


# ---------- output ----------


@dataclass
class Dimension:
    key: str
    label: str
    points: int
    max: int
    reason: str
    evidence_ids: list[str] = field(default_factory=list)
    record_ids: list[str] = field(default_factory=list)  # "wtp:…", "competitor:…", "interview:…"
    gaps: list[str] = field(default_factory=list)


@dataclass
class Point:
    """A line of strong or weak evidence, with what backs it."""

    text: str
    evidence_ids: list[str] = field(default_factory=list)
    record_ids: list[str] = field(default_factory=list)


@dataclass
class Decision:
    recommendation: str  # build | iterate | investigate | abandon
    headline: str
    why: str
    strong: list[Point]
    weak: list[Point]
    uncertainty: str
    next_actions: list[str]


@dataclass
class Evaluation:
    total: int
    dimensions: list[Dimension]
    state: str
    decision: Decision
    metrics: dict
    facts: dict  # the counts the rules used; the report quotes only these numbers
    inputs_hash: str
    scoring_version: int = SCORING_VERSION

    def as_dict(self) -> dict:
        return asdict(self)


# ---------- helpers ----------


def _clamp(v: int, hi: int) -> int:
    return max(0, min(hi, v))


def _plural(n: int, word: str, plural: str | None = None) -> str:
    return f"{n} {word if n == 1 else (plural or word + 's')}"


def _uniq(ids: list[str]) -> list[str]:
    return list(dict.fromkeys(ids))


@dataclass
class _Customers:
    """Per-customer view of the first-party signals."""

    confirm: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    deny: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    by_field: dict[str, dict[str, list[CustomerSignal]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(list))
    )
    company: dict[str, str] = field(default_factory=dict)


def _customers(inp: ValidationInput) -> _Customers:
    c = _Customers()
    for s in inp.signals:
        c.company.setdefault(s.customer, s.company)
        if s.field == "problem_confirmed":
            (c.confirm if s.value == "yes" else c.deny)[s.customer].append(s.evidence_id)
        else:
            c.by_field[s.field][s.customer].append(s)
    # A customer who both confirms and denies (e.g. reply vs interview) counts as confirming;
    # the denial still shows up as weak evidence through `mixed`.
    return c


def _confirming(c: _Customers) -> dict[str, list[str]]:
    return dict(c.confirm)


def _denying(c: _Customers) -> dict[str, list[str]]:
    return {k: v for k, v in c.deny.items() if k not in c.confirm}


def _research(inp: ValidationInput, stance: str, categories: tuple[str, ...] | None = None):
    return [
        r
        for r in inp.research
        if r.verification == "verified"
        and r.stance == stance
        and (categories is None or set(r.unknown_categories) & set(categories))
    ]


def _domains(items: list[ResearchItem]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for r in items:
        out[r.domain].append(r.evidence_id)
    return dict(out)


def _best_level(signals: list[CustomerSignal]) -> str:
    return max((s.value for s in signals), key=lambda v: LEVEL_ORDER.get(v, 0), default="")


def _done_interviews_confirming(inp: ValidationInput) -> dict[str, list[str]]:
    done = {i.interview_id for i in inp.interviews if i.done}
    out: dict[str, list[str]] = defaultdict(list)
    for s in inp.signals:
        if s.origin != "interview" or s.source_id not in done:
            continue
        if (s.field == "problem_confirmed" and s.value == "yes") or s.field in (
            "frequency",
            "cost",
        ):
            out[s.source_id].append(s.evidence_id)
    return dict(out)


def _wtp_by_customer(inp: ValidationInput) -> dict[str, list[WtpInput]]:
    out: dict[str, list[WtpInput]] = defaultdict(list)
    for w in inp.wtp:
        out[w.customer].append(w)
    return dict(out)


def _wtp_points(rows: list[WtpInput]) -> int:
    best = 0
    for w in rows:
        best = max(
            best,
            WTP_COMMITMENT_POINTS.get(w.commitment, 0),
            WTP_STATED_POINTS.get(w.stated, 0),
        )
    if best == 0 and any(w.stated == "none" for w in rows):
        return -WTP_STATED_NONE_PENALTY
    return best


# ---------- dimensions ----------


def _problem(inp: ValidationInput, c: _Customers) -> Dimension:
    confirm, deny = _confirming(c), _denying(c)
    support = _domains([r for r in _research(inp, "supports") if r.relevance in ("high", "medium")])
    contra = _domains(_research(inp, "contradicts"))
    pts = (
        min(PROBLEM_CUSTOMER_MAX, PROBLEM_PER_CUSTOMER * len(confirm))
        + min(PROBLEM_DOMAIN_MAX, PROBLEM_PER_DOMAIN * len(support))
        - PROBLEM_DENIAL_PENALTY * len(deny)
        - PROBLEM_CONTRA_DOMAIN_PENALTY * len(contra)
    )
    reason = (
        f"{_plural(len(confirm), 'customer')} confirmed the problem, "
        f"{_plural(len(deny), 'denied', 'denied')} it; "
        f"{_plural(len(support), 'independent source')} support it, "
        f"{len(contra)} contradict it."
    )
    gaps = []
    if len(confirm) * PROBLEM_PER_CUSTOMER < PROBLEM_CUSTOMER_MAX:
        gaps.append("More customers confirming the problem in their own words.")
    if len(support) * PROBLEM_PER_DOMAIN < PROBLEM_DOMAIN_MAX:
        gaps.append("More independent public sources describing the problem.")
    ids = [e for v in confirm.values() for e in v] + [e for v in support.values() for e in v]
    ids += [e for v in deny.values() for e in v] + [e for v in contra.values() for e in v]
    return Dimension(
        "problem_evidence", "Problem evidence", _clamp(pts, 20), 20, reason, _uniq(ids), [], gaps
    )


def _frequency(inp: ValidationInput, c: _Customers) -> Dimension:
    customers = c.by_field["frequency"]
    research = _research(inp, "supports", ("frequency",))
    pts = min(FREQ_CUSTOMER_MAX, FREQ_PER_CUSTOMER * len(customers)) + min(
        FREQ_RESEARCH_MAX, FREQ_PER_RESEARCH * len(research)
    )
    reason = (
        f"{_plural(len(customers), 'customer')} said how often it happens; "
        f"{_plural(len(research), 'research item')} on frequency."
    )
    gaps = [] if pts >= 10 else ["Ask customers how often the problem happens."]
    ids = [s.evidence_id for v in customers.values() for s in v] + [r.evidence_id for r in research]
    return Dimension(
        "frequency", "Problem frequency", _clamp(pts, 10), 10, reason, _uniq(ids), [], gaps
    )


def _severity(inp: ValidationInput, c: _Customers) -> Dimension:
    sev, cost = c.by_field["severity"], c.by_field["cost"]
    customer_pts = 0
    for cust in set(sev) | set(cost):
        customer_pts += SEVERITY_POINTS.get(_best_level(sev.get(cust, [])), 0)
        customer_pts += SEVERITY_COST_BONUS if cust in cost else 0
    research = _research(inp, "supports", ("cost", "urgency"))
    pts = min(SEVERITY_CUSTOMER_MAX, customer_pts) + min(
        SEVERITY_RESEARCH_MAX, SEVERITY_PER_RESEARCH * len(research)
    )
    high = sum(1 for v in sev.values() if _best_level(v) == "high")
    low = sum(1 for v in sev.values() if _best_level(v) == "low")
    reason = (
        f"{_plural(high, 'customer')} called it severe, {low} minor; "
        f"{_plural(len(cost), 'customer')} put a time or cost on it; "
        f"{_plural(len(research), 'research item')} on cost or urgency."
    )
    gaps = [] if pts >= 15 else ["Ask what the problem costs them in time or money."]
    ids = [s.evidence_id for d in (sev, cost) for v in d.values() for s in v]
    ids += [r.evidence_id for r in research]
    return Dimension(
        "severity", "Problem severity", _clamp(pts, 15), 15, reason, _uniq(ids), [], gaps
    )


def _engaged(inp: ValidationInput, c: _Customers) -> dict[str, list[str]]:
    """Customers with a positive reply or high/medium interest, with the evidence behind it."""
    out: dict[str, list[str]] = defaultdict(list)
    for r in inp.replies:
        if r.sentiment == "positive" and r.evidence_ids and not r.opt_out:
            out[r.customer].extend(r.evidence_ids)
    for cust, sigs in c.by_field["interest"].items():
        for s in sigs:
            if s.value in ("high", "medium"):
                out[cust].append(s.evidence_id)
    return dict(out)


def _response(inp: ValidationInput, c: _Customers) -> Dimension:
    engaged = _engaged(inp, c)
    pts = min(RESPONSE_CUSTOMER_MAX, RESPONSE_PER_CUSTOMER * len(engaged))
    rate = inp.replied_messages / inp.sent if inp.sent else None
    if inp.sent >= RESPONSE_MIN_SENT and rate is not None:
        if rate >= RESPONSE_RATE_HIGH:
            pts += RESPONSE_RATE_HIGH_POINTS
        elif rate >= RESPONSE_RATE_LOW:
            pts += RESPONSE_RATE_LOW_POINTS
    rate_txt = (
        f"{round(rate * 100)}% reply rate on {inp.sent} sent"
        if rate is not None
        else ("no outreach sent")
    )
    reason = (
        f"{_plural(len(engaged), 'customer')} replied positively or showed interest; {rate_txt}."
    )
    gaps = []
    if inp.sent < RESPONSE_MIN_SENT:
        gaps.append(f"Send outreach to at least {RESPONSE_MIN_SENT} prospects.")
    if len(engaged) * RESPONSE_PER_CUSTOMER < RESPONSE_CUSTOMER_MAX:
        gaps.append("More engaged replies (positive, or asking to talk).")
    ids = [e for v in engaged.values() for e in v]
    return Dimension(
        "customer_response", "Customer response", _clamp(pts, 15), 15, reason, _uniq(ids), [], gaps
    )


def _interviews(inp: ValidationInput) -> Dimension:
    confirming = _done_interviews_confirming(inp)
    done = [i for i in inp.interviews if i.done]
    pts = min(INTERVIEW_MAX, INTERVIEW_POINTS * len(confirming))
    reason = (
        f"{_plural(len(done), 'interview')} done, "
        f"{len(confirming)} with the customer describing the problem, its frequency or cost."
    )
    gaps = [] if pts >= INTERVIEW_MAX else ["Complete interviews that probe the problem."]
    ids = [e for v in confirming.values() for e in v]
    return Dimension(
        "interview_confirmation",
        "Interview confirmation",
        _clamp(pts, 15),
        15,
        reason,
        _uniq(ids),
        [f"interview:{i}" for i in confirming],
        gaps,
    )


def _alternatives(inp: ValidationInput, c: _Customers) -> Dimension:
    naming = c.by_field["current_solution"]
    satisfied = {
        k: v for k, v in c.by_field["solution_satisfaction"].items() if _best_level(v) == "high"
    }
    comps = [x for x in inp.competitors if x.evidence_ids]
    pts = (
        min(ALT_CUSTOMER_MAX, ALT_PER_CUSTOMER * len(naming))
        + min(ALT_COMPETITOR_MAX, ALT_PER_COMPETITOR * len(comps))
        - ALT_SATISFIED_PENALTY * len(satisfied)
    )
    reason = (
        f"{_plural(len(naming), 'customer')} described what they use today; "
        f"{_plural(len(comps), 'alternative')} mapped with evidence; "
        f"{len(satisfied)} happy with their current solution."
    )
    gaps = [] if pts >= 10 else ["Ask what they use today and how well it works."]
    ids = [s.evidence_id for d in (naming, satisfied) for v in d.values() for s in v]
    ids += [e for x in comps for e in x.evidence_ids]
    return Dimension(
        "alternatives",
        "Existing alternatives",
        _clamp(pts, 10),
        10,
        reason,
        _uniq(ids),
        [f"competitor:{x.competitor_id}" for x in comps],
        gaps,
    )


def _wtp(inp: ValidationInput) -> Dimension:
    by_cust = _wtp_by_customer(inp)
    pts = sum(_wtp_points(v) for v in by_cust.values())
    committed = [k for k, v in by_cust.items() if any(w.commitment in PILOT_OR_BETTER for w in v)]
    stated = [k for k, v in by_cust.items() if any(w.stated in ("strong", "some") for w in v)]
    reason = (
        f"{_plural(len(committed), 'customer')} committed to a pilot or more; "
        f"{_plural(len(stated), 'customer')} said they would pay."
    )
    gaps = [] if pts >= 15 else ["Ask for a pilot, a signed commitment or a payment."]
    ids = [w.evidence_id for v in by_cust.values() for w in v if w.evidence_id]
    recs = [f"wtp:{w.wtp_id}" for v in by_cust.values() for w in v]
    return Dimension(
        "willingness_to_pay",
        "Willingness to pay",
        _clamp(pts, 15),
        15,
        reason,
        _uniq(ids),
        recs,
        gaps,
    )


# ---------- facts, state, decision, metrics ----------


def _facts(inp: ValidationInput, c: _Customers) -> dict:
    confirm, deny = _confirming(c), _denying(c)
    confirm_companies = {c.company[k] for k in confirm}
    confirm_interview = {
        s.company
        for s in inp.signals
        if s.origin == "interview"
        and s.field == "problem_confirmed"
        and s.value == "yes"
        and s.source_id in {i.interview_id for i in inp.interviews if i.done}
    }
    high_interest = {k for k, v in c.by_field["interest"].items() if _best_level(v) == "high"}
    by_wtp = _wtp_by_customer(inp)
    pilots = sum(1 for v in by_wtp.values() if any(w.commitment in PILOT_OR_BETTER for w in v))
    paid = sum(1 for v in by_wtp.values() if any(w.commitment == "paid" for w in v))
    no_wtp = sum(
        1 for v in by_wtp.values() if any(w.stated == "none" for w in v) and _wtp_points(v) <= 0
    )
    satisfied = sum(
        1 for v in c.by_field["solution_satisfaction"].values() if _best_level(v) == "high"
    )
    support_domains = _domains(_research(inp, "supports"))
    conversations = {s.customer for s in inp.signals} | {
        r.customer for r in inp.replies if r.evidence_ids
    }
    return {
        "confirming_customers": len(confirm),
        "denying_customers": len(deny),
        "confirming_companies": len(confirm_companies),
        "confirming_in_interview": len(confirm_interview),
        "supporting_domains": len(support_domains),
        "high_interest_customers": len(high_interest),
        "pilot_or_better": pilots,
        "paid": paid,
        "no_wtp_customers": no_wtp,
        "satisfied_customers": satisfied,
        "interviews_done": sum(1 for i in inp.interviews if i.done),
        "validated_conversations": len(conversations),
        "sent": inp.sent,
        "replies": len(inp.replies),
        "unverifiable_research": sum(1 for r in inp.research if r.verification == "unverifiable"),
        "open_unknowns": len(inp.open_unknowns),
    }


def _problem_validated(f: dict) -> bool:
    return (
        f["confirming_companies"] >= PROBLEM_VALIDATED_COMPANIES
        and f["confirming_in_interview"] >= PROBLEM_VALIDATED_INTERVIEWS
        and f["confirming_customers"] >= CONFIRM_TO_DENY_RATIO * f["denying_customers"]
    )


def validation_state(inp: ValidationInput, f: dict, total: int) -> str:
    if _problem_validated(f):
        commercial = f["pilot_or_better"] >= COMMERCIAL_PILOTS or f["paid"] >= COMMERCIAL_PAID
        if commercial and total >= MVP_SCORE and f["interviews_done"] >= MVP_INTERVIEWS:
            return "mvp_ready"
        if commercial:
            return "commercial_validation"
        if f["high_interest_customers"] >= SOLUTION_HIGH_INTEREST:
            return "solution_validation"
        return "problem_validated"
    if f["confirming_customers"] >= EARLY_CUSTOMERS or f["supporting_domains"] >= EARLY_DOMAINS:
        return "early_signal"
    if inp.has_research:
        return "researching"
    return "unvalidated"


_HEADLINES = {
    "build": "Strong evidence. Build the MVP.",
    "abandon": "Customers contradict the problem. Stop or pivot.",
    "iterate": "Mixed evidence. Change the idea or the ICP before building.",
}

_PRIORITY = {"high": 0, "medium": 1, "low": 2}


def _recommendation(f: dict, state: str) -> tuple[str, str]:
    """(recommendation, why) from the facts. Absence of evidence never leads to abandon."""
    confirm, deny = f["confirming_customers"], f["denying_customers"]
    if state == "mvp_ready":
        return "build", "The problem, interest and commitments all meet the MVP-ready thresholds."
    if deny >= ABANDON_DENIALS and deny >= confirm:
        return "abandon", (
            f"{_plural(deny, 'customer')} said they don't have this problem, "
            f"against {confirm} confirming it."
        )
    if deny and confirm < CONFIRM_TO_DENY_RATIO * deny:
        return "iterate", (
            f"{confirm} confirming vs {deny} denying the problem: not yet the "
            f"{CONFIRM_TO_DENY_RATIO}-to-1 the evidence needs."
        )
    if (
        _problem_validated(f)
        and f["no_wtp_customers"] >= ITERATE_NO_WTP
        and not f["pilot_or_better"]
    ):
        return "iterate", (
            f"The problem is validated, but {f['no_wtp_customers']} customers said they "
            "wouldn't pay and nobody has committed."
        )
    if f["satisfied_customers"] >= ITERATE_SATISFIED:
        return "iterate", (
            f"{f['satisfied_customers']} customers are happy with what they use today."
        )
    return "investigate", "The evidence doesn't yet meet the thresholds for a decision."


def _points(
    dims: list[Dimension], f: dict, inp: ValidationInput
) -> tuple[list[Point], list[Point]]:
    strong: list[Point] = []
    weak: list[Point] = []
    for d in dims:
        target = strong if d.points >= d.max / 2 else weak
        target.append(
            Point(f"{d.label} {d.points}/{d.max}: {d.reason}", d.evidence_ids, d.record_ids)
        )
    if f["denying_customers"]:
        weak.append(Point(f"{_plural(f['denying_customers'], 'customer')} denied the problem."))
    if f["satisfied_customers"]:
        weak.append(Point(f"{f['satisfied_customers']} happy with their current solution."))
    objections = [s for s in inp.signals if s.field == "objection"]
    if objections:
        weak.append(
            Point(
                f"{_plural(len(objections), 'objection')} raised in interviews.",
                _uniq([s.evidence_id for s in objections]),
            )
        )
    stated_only = [
        w for w in inp.wtp if w.stated in ("strong", "some") and w.commitment not in PILOT_OR_BETTER
    ]
    if stated_only:
        weak.append(
            Point(
                f"{_plural(len(stated_only), 'customer')} said they'd pay but hasn't committed.",
                _uniq([w.evidence_id for w in stated_only if w.evidence_id]),
                [f"wtp:{w.wtp_id}" for w in stated_only],
            )
        )
    if f["unverifiable_research"]:
        weak.append(
            Point(f"{_plural(f['unverifiable_research'], 'research item')} couldn't be verified.")
        )
    return strong, weak


def _uncertainty(dims: list[Dimension], inp: ValidationInput) -> str:
    # PRD weight order breaks ties: dims are already in that order and max() keeps the first.
    worst = max(dims, key=lambda d: d.max - d.points)
    if worst.points == worst.max:
        return "No dimension is missing points."
    text = f"{worst.label}: {worst.points}/{worst.max}. {worst.reason}"
    if inp.open_unknowns:
        top = min(inp.open_unknowns, key=lambda u: _PRIORITY.get(u.priority, 3))
        text += f" Top open question: {top.question}"
    return text


def _next_actions(dims: list[Dimension], f: dict, inp: ValidationInput) -> list[str]:
    actions: list[str] = []
    need = PROBLEM_VALIDATED_COMPANIES - f["confirming_companies"]
    if need > 0:
        actions.append(
            f"Get {_plural(need, 'more independent company', 'more independent companies')} "
            f"to confirm the problem ({f['confirming_companies']} so far)."
        )
    if f["confirming_in_interview"] < PROBLEM_VALIDATED_INTERVIEWS:
        actions.append("Hold an interview where the customer describes the problem in their words.")
    if inp.sent < RESPONSE_MIN_SENT:
        actions.append(
            f"Send outreach to at least {RESPONSE_MIN_SENT} prospects ({inp.sent} sent)."
        )
    for d in sorted(dims, key=lambda d: d.points - d.max):
        if d.points < d.max and d.gaps and d.gaps[0] not in actions:
            actions.append(d.gaps[0])
        if len(actions) >= 5:
            break
    for u in sorted(inp.open_unknowns, key=lambda u: _PRIORITY.get(u.priority, 3))[:3]:
        actions.append(f"Find out: {u.question}")
    return _uniq(actions)


def metrics(inp: ValidationInput, f: dict) -> dict:
    def ratio(a: int, b: int) -> float | None:
        return round(a / b, 3) if b else None

    positive = sum(1 for r in inp.replies if r.sentiment == "positive")
    return {
        "validated_conversations": f["validated_conversations"],
        "response_rate": ratio(inp.replied_messages, inp.sent),
        "problem_confirmation_rate": ratio(f["confirming_customers"], f["validated_conversations"]),
        "interview_conversion": ratio(f["interviews_done"], positive),
        "commercial_validation": ratio(f["pilot_or_better"], f["validated_conversations"]),
    }


def _hash(inp: ValidationInput) -> str:
    payload = json.dumps(
        {"v": SCORING_VERSION, "inputs": canonical(inp)}, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def canonical(inp: ValidationInput) -> dict:
    """The inputs as sorted JSON-ready data: order of rows in the DB doesn't change the hash."""
    data = asdict(inp)
    for k, v in data.items():
        if isinstance(v, (list, tuple)):
            data[k] = sorted(v, key=lambda x: json.dumps(x, sort_keys=True))
    return data


def evaluate(inp: ValidationInput) -> Evaluation:
    c = _customers(inp)
    dims = [
        _problem(inp, c),
        _frequency(inp, c),
        _severity(inp, c),
        _response(inp, c),
        _interviews(inp),
        _alternatives(inp, c),
        _wtp(inp),
    ]
    total = sum(d.points for d in dims)
    f = _facts(inp, c)
    state = validation_state(inp, f, total)
    rec, why = _recommendation(f, state)
    if rec == "investigate":
        headline = (
            "Weak evidence. Don't build yet."
            if total < WEAK_SCORE
            else "Promising, but not enough evidence yet. Don't build yet."
        )
    else:
        headline = _HEADLINES[rec]
    strong, weak = _points(dims, f, inp)
    decision = Decision(
        recommendation=rec,
        headline=headline,
        why=why,
        strong=strong,
        weak=weak,
        uncertainty=_uncertainty(dims, inp),
        next_actions=[] if rec == "build" else _next_actions(dims, f, inp),
    )
    return Evaluation(
        total=total,
        dimensions=dims,
        state=state,
        decision=decision,
        metrics=metrics(inp, f),
        facts=f,
        inputs_hash=_hash(inp),
    )
