"""Pure tests for the validation score, state and decision (PRD §24–§26)."""

import random
from dataclasses import replace

from app.modules.validation.scoring import (
    CompetitorInput,
    CustomerSignal,
    InterviewInput,
    ReplyInput,
    ResearchItem,
    UnknownInput,
    ValidationInput,
    WtpInput,
    evaluate,
)

_n = 0


def _id() -> str:
    global _n
    _n += 1
    return f"ev-{_n}"


def sig(customer: str, field: str, value: str = "", *, origin="reply", source=None, company=None):
    return CustomerSignal(
        evidence_id=_id(),
        customer=customer,
        company=company or f"co-{customer}",
        origin=origin,
        source_id=source or f"src-{customer}-{origin}",
        field=field,
        value=value,
    )


def research(domain: str, stance="supports", cats=(), verification="verified", relevance="high"):
    return ResearchItem(_id(), domain, stance, relevance, verification, tuple(cats))


def interviewed(customer: str, *fields: tuple[str, str]):
    """A done interview with the given (field, value) signals."""
    iid = f"int-{customer}"
    signals = [sig(customer, f, v, origin="interview", source=iid) for f, v in fields]
    return InterviewInput(iid, customer, f"co-{customer}", True), signals


WEAK = ValidationInput(
    has_research=True,
    research=(research("a.com"), research("b.com", verification="unverifiable")),
    signals=(sig("c1", "problem_confirmed", "yes"),),
    replies=(ReplyInput("r1", "c1", "neutral", False, ("x",)),),
    sent=12,
    replied_messages=1,
    open_unknowns=(UnknownInput("u1", "Who approves the reports?", "high", "buyer"),),
)


def strong_input() -> ValidationInput:
    interviews, signals = [], []
    for c in ("c1", "c2", "c3", "c4", "c5"):
        i, s = interviewed(
            c,
            ("problem_confirmed", "yes"),
            ("frequency", "weekly"),
            ("cost", "4 hours"),
            ("current_solution", "Excel"),
        )
        interviews.append(i)
        signals.extend(s)
        signals.append(sig(c, "severity", "high"))
        signals.append(sig(c, "interest", "high"))
    return ValidationInput(
        has_research=True,
        research=tuple(research(f"{d}.com", cats=("frequency", "cost")) for d in "abcd"),
        signals=tuple(signals),
        replies=tuple(
            ReplyInput(f"r{c}", c, "positive", False, (_id(),))
            for c in ("c1", "c2", "c3", "c4", "c5")
        ),
        interviews=tuple(interviews),
        wtp=(
            WtpInput("w1", "c1", "strong", "pilot", None),
            WtpInput("w2", "c2", "strong", "paid", None),
        ),
        competitors=tuple(CompetitorInput(f"k{i}", f"K{i}", (_id(),)) for i in range(4)),
        sent=30,
        replied_messages=6,
    )


def test_same_inputs_same_output_regardless_of_row_order():
    inp = strong_input()
    shuffled = replace(
        inp,
        signals=tuple(random.Random(1).sample(inp.signals, len(inp.signals))),
        research=tuple(reversed(inp.research)),
    )
    a, b = evaluate(inp), evaluate(shuffled)
    assert a.inputs_hash == b.inputs_hash
    assert a.total == b.total
    assert [d.points for d in a.dimensions] == [d.points for d in b.dimensions]
    assert a.as_dict()["decision"]["recommendation"] == b.as_dict()["decision"]["recommendation"]
    assert evaluate(inp).as_dict() == evaluate(inp).as_dict()


def test_hash_changes_when_inputs_change():
    inp = strong_input()
    assert evaluate(inp).inputs_hash != evaluate(replace(inp, sent=31)).inputs_hash


def test_weak_evidence_is_told_not_to_build_yet():
    e = evaluate(WEAK)
    assert e.total < 40
    assert e.decision.recommendation == "investigate"
    assert e.decision.headline == "Weak evidence. Don't build yet."
    assert e.state == "early_signal"
    # it explains itself: weak spots, the biggest uncertainty and what to do next
    assert any("couldn't be verified" in p.text for p in e.decision.weak)
    assert e.decision.uncertainty
    assert any("Who approves" in a for a in e.decision.next_actions)
    assert any("more independent companies" in a for a in e.decision.next_actions)


def test_dimension_weights_match_prd():
    e = evaluate(WEAK)
    assert [(d.key, d.max) for d in e.dimensions] == [
        ("problem_evidence", 20),
        ("frequency", 10),
        ("severity", 15),
        ("customer_response", 15),
        ("interview_confirmation", 15),
        ("alternatives", 10),
        ("willingness_to_pay", 15),
    ]
    assert sum(d.max for d in e.dimensions) == 100


def test_every_dimension_cites_what_it_counted():
    e = evaluate(strong_input())
    for d in e.dimensions:
        if d.points > 0:
            assert d.evidence_ids or d.record_ids, d.key
        assert d.reason


def test_strong_input_is_mvp_ready_and_build():
    e = evaluate(strong_input())
    assert e.total >= 70
    assert e.state == "mvp_ready"
    assert e.decision.recommendation == "build"
    assert e.decision.strong and all(p.evidence_ids or p.record_ids for p in e.decision.strong)


def test_one_customer_quoting_many_times_counts_once():
    many = ValidationInput(
        has_research=True,
        signals=tuple(sig("c1", "problem_confirmed", "yes") for _ in range(5)),
    )
    e = evaluate(many)
    assert e.facts["confirming_customers"] == 1
    assert e.dimensions[0].points == 3


def test_unverified_and_dismissed_research_doesnt_score():
    inp = ValidationInput(
        has_research=True,
        research=tuple(research(f"{d}.com", verification="unverifiable") for d in "abc"),
    )
    e = evaluate(inp)
    assert e.dimensions[0].points == 0
    assert e.state == "researching"


def test_state_unvalidated_without_anything():
    assert evaluate(ValidationInput(has_research=False)).state == "unvalidated"


def test_state_early_signal_from_three_independent_domains():
    inp = ValidationInput(
        has_research=True, research=(research("a.com"), research("a.com"), research("b.com"))
    )
    assert evaluate(inp).state == "researching"  # two domains only
    inp = replace(inp, research=inp.research + (research("c.com"),))
    assert evaluate(inp).state == "early_signal"


def _problem_validated(n_companies=3, interview=True, extra=()):
    signals, interviews = [], []
    for i in range(n_companies):
        c = f"c{i}"
        if interview and i == 0:
            iv, s = interviewed(c, ("problem_confirmed", "yes"))
            interviews.append(iv)
            signals.extend(s)
        else:
            signals.append(sig(c, "problem_confirmed", "yes"))
    return ValidationInput(
        has_research=True, signals=tuple(signals) + tuple(extra), interviews=tuple(interviews)
    )


def test_problem_validated_needs_three_companies_and_an_interview():
    assert evaluate(_problem_validated()).state == "problem_validated"
    assert evaluate(_problem_validated(n_companies=2)).state == "early_signal"
    assert evaluate(_problem_validated(interview=False)).state == "early_signal"


def test_problem_validated_needs_independent_companies():
    # three people at the same company are one company
    inp = _problem_validated()
    same = replace(inp, signals=tuple(replace(s, company="co-same") for s in inp.signals))
    assert evaluate(same).state == "early_signal"


def test_problem_validated_needs_two_to_one_confirmations():
    denials = tuple(sig(f"d{i}", "problem_confirmed", "no") for i in range(2))
    e = evaluate(_problem_validated(extra=denials))
    assert e.state == "early_signal"
    assert e.decision.recommendation == "iterate"


def test_solution_validation_from_high_interest():
    extra = tuple(sig(f"c{i}", "interest", "high") for i in range(3))
    assert evaluate(_problem_validated(extra=extra)).state == "solution_validation"


def test_commercial_validation_from_two_pilots_or_one_payment():
    inp = _problem_validated()
    pilots = (
        WtpInput("w1", "c0", "unknown", "pilot", None),
        WtpInput("w2", "c1", "unknown", "pilot", None),
    )
    assert evaluate(replace(inp, wtp=pilots)).state == "commercial_validation"
    assert evaluate(replace(inp, wtp=pilots[:1])).state == "problem_validated"
    paid = (WtpInput("w3", "c2", "unknown", "paid", None),)
    assert evaluate(replace(inp, wtp=paid)).state == "commercial_validation"


def test_stated_willingness_alone_is_not_commercial_validation():
    inp = _problem_validated()
    stated = tuple(WtpInput(f"w{i}", f"c{i}", "strong", "none", None) for i in range(3))
    e = evaluate(replace(inp, wtp=stated))
    assert e.state == "problem_validated"
    assert any("hasn't committed" in p.text or "haven't" in p.text for p in e.decision.weak)


def test_mvp_ready_needs_score_and_five_interviews():
    inp = strong_input()
    four = replace(inp, interviews=inp.interviews[:4])
    assert evaluate(four).state == "commercial_validation"
    assert evaluate(four).decision.recommendation != "build"


def test_abandon_only_on_active_contradiction():
    denials = tuple(sig(f"d{i}", "problem_confirmed", "no") for i in range(3))
    e = evaluate(ValidationInput(has_research=True, signals=denials))
    assert e.decision.recommendation == "abandon"
    # silence is not rejection: lots of outreach and no replies is "investigate"
    e = evaluate(ValidationInput(has_research=True, sent=200, replied_messages=0))
    assert e.decision.recommendation == "investigate"


def test_iterate_when_customers_are_happy_with_current_solution():
    happy = tuple(sig(f"c{i}", "solution_satisfaction", "high") for i in range(2))
    e = evaluate(_problem_validated(extra=happy))
    assert e.decision.recommendation == "iterate"
    assert e.dimensions[5].points == 0


def test_interview_with_only_objections_scores_nothing_but_is_weak_evidence():
    iv, s = interviewed("c1", ("objection", "too expensive"))
    e = evaluate(ValidationInput(has_research=True, signals=tuple(s), interviews=(iv,)))
    assert e.dimensions[4].points == 0
    assert any("objection" in p.text for p in e.decision.weak)


def test_reply_rate_points_need_a_minimum_sample():
    small = ValidationInput(has_research=True, sent=5, replied_messages=5)
    assert evaluate(small).dimensions[3].points == 0
    big = ValidationInput(has_research=True, sent=20, replied_messages=3)
    assert evaluate(big).dimensions[3].points == 5


def test_metrics():
    m = evaluate(strong_input()).metrics
    assert m["validated_conversations"] == 5
    assert m["response_rate"] == 0.2
    assert m["problem_confirmation_rate"] == 1.0
    assert m["interview_conversion"] == 1.0
    assert m["commercial_validation"] == 0.4
    assert evaluate(ValidationInput(has_research=False)).metrics["response_rate"] is None


def test_wtp_points_take_the_best_per_customer():
    rows = (
        WtpInput("w1", "c1", "strong", "verbal", None),
        WtpInput("w2", "c1", "unknown", "pilot", None),
        WtpInput("w3", "c2", "none", "none", None),
    )
    e = evaluate(ValidationInput(has_research=True, wtp=rows))
    assert e.dimensions[6].points == 8 - 2


def test_stored_inputs_rescore_to_the_same_result():
    import json

    from app.modules.validation.scoring import canonical, from_canonical

    inp = strong_input()
    stored = json.loads(json.dumps(canonical(inp)))  # as it comes back from a JSON column
    assert evaluate(from_canonical(stored)).as_dict() == evaluate(inp).as_dict()
