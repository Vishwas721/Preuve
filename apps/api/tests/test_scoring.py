from dataclasses import replace

import pytest

from app.modules.prospects.scoring import (
    AssessmentInput,
    ICPTarget,
    LinkedEvidence,
    ScoringInput,
    role_matches,
    score,
)

ICP = ICPTarget(
    name="Mid-size GCs",
    size_min=50,
    size_max=500,
    user_roles=("Construction Project Managers", "Project Engineers"),
    buyer_roles=("CFO", "VP of Construction Operations"),
)


def base(**overrides) -> ScoringInput:
    inp = ScoringInput(
        company_fit=AssessmentInput(4, "Commercial GC", ("e1",)),
        technology_fit=AssessmentInput(5, "Uses Procore", ("e2",)),
        other_signals=AssessmentInput(0, "None", ()),
        linked_evidence=(
            LinkedEvidence("e3", "verified", "supports"),
            LinkedEvidence("e4", "unverifiable", "supports"),
            LinkedEvidence("e5", "verified", "neutral"),
        ),
        contact_roles=("Senior Project Manager",),
        size_min=200,
        size_max=None,
        size_signal="About page: 200+ employees",
        size_evidence_id="e1",
        in_geo=True,
        geo_evidence_id="e1",
        icp=ICP,
    )
    return replace(inp, **overrides)


def by_key(result) -> dict:
    return {c.key: c for c in result.components}


def test_full_breakdown_and_total() -> None:
    result = score(base())
    c = by_key(result)
    assert c["company_fit"].points == 16 and c["company_fit"].evidence_ids == ["e1"]
    assert c["problem_evidence"].points == 15  # 1 verified + 0.5 unverifiable = 1.5
    assert c["problem_evidence"].evidence_ids == ["e3", "e4"]
    assert c["role_relevance"].points == 12  # matches a user role, not a buyer role
    assert c["company_size"].points == 5  # 200..inf overlaps 50..500
    assert c["geography"].points == 5
    assert c["technology_fit"].points == 10
    assert c["other_signals"].points == 0
    assert result.total == 63
    assert all(comp.reason for comp in result.components)
    assert sum(comp.max for comp in result.components) == 100


def test_deterministic_and_hash_tracks_inputs() -> None:
    a, b = score(base()), score(base())
    assert (a.total, a.inputs_hash) == (b.total, b.inputs_hash)
    assert score(base(size_max=400)).inputs_hash != a.inputs_hash


def test_assessment_without_evidence_scores_zero() -> None:
    result = score(base(company_fit=AssessmentInput(5, "Looks perfect", ())))
    fit = by_key(result)["company_fit"]
    assert fit.points == 0 and "no stored evidence" in fit.reason


@pytest.mark.parametrize(
    ("weights", "points"),
    [((), 0), (("unverifiable",), 8), (("verified",), 15), (("verified", "verified"), 25)],
)
def test_problem_evidence_tiers(weights: tuple, points: int) -> None:
    linked = tuple(LinkedEvidence(f"e{i}", v, "supports") for i, v in enumerate(weights))
    assert by_key(score(base(linked_evidence=linked)))["problem_evidence"].points == points


def test_contradicting_evidence_does_not_count() -> None:
    linked = (LinkedEvidence("e1", "verified", "contradicts"),)
    assert by_key(score(base(linked_evidence=linked)))["problem_evidence"].points == 0


@pytest.mark.parametrize(
    ("roles", "points"),
    [
        (("Chief Financial Officer",), 20),
        # "construction" is an industry qualifier, so VP + operations matches the buyer role
        (("Vice President of Operations",), 20),
        (("Project Engineer",), 12),
        (("Marketing Coordinator",), 5),
        ((), 0),
    ],
)
def test_role_relevance(roles: tuple, points: int) -> None:
    assert by_key(score(base(contact_roles=roles)))["role_relevance"].points == points


def test_role_matching_rules() -> None:
    assert role_matches("Construction Project Managers", "Senior Project Manager")
    assert role_matches("CFO", "Chief Financial Officer")
    assert role_matches("Operations Director", "Director of Operations")
    assert not role_matches("Project Manager", "Operations Manager")
    assert not role_matches("Construction", "Construction Manager")  # nothing significant left


@pytest.mark.parametrize(
    ("size_min", "size_max", "points"),
    [(100, 300, 10), (300, 800, 5), (600, 900, 0), (None, None, 0), (None, 40, 0)],
)
def test_size_bands(size_min, size_max, points) -> None:
    assert (
        by_key(score(base(size_min=size_min, size_max=size_max)))["company_size"].points == points
    )


def test_size_without_icp_band_is_neutral() -> None:
    icp = replace(ICP, size_min=None, size_max=None)
    assert by_key(score(base(icp=icp)))["company_size"].points == 5


def test_geography_needs_evidence() -> None:
    assert by_key(score(base(geo_evidence_id=None)))["geography"].points == 0
    assert by_key(score(base(in_geo=False)))["geography"].points == 0


def test_no_icp_still_scores() -> None:
    result = score(base(icp=None))
    assert by_key(result)["role_relevance"].points == 5
    assert by_key(result)["company_size"].points == 5


def test_zero_rating_reads_as_a_rating_not_missing_evidence() -> None:
    comp = by_key(score(base(other_signals=AssessmentInput(0, "No public signals.", ()))))
    assert comp["other_signals"].points == 0
    assert comp["other_signals"].reason == "0/5: No public signals."
