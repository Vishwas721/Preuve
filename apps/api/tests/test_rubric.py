import pytest
from pydantic import ValidationError

from app.modules.analysis.rubric import Criterion, Rating, compute_score, rubric_prompt_lines


def ratings(**overrides: int) -> dict[Criterion, Rating]:
    values = {c: 3 for c in Criterion} | {Criterion(k): v for k, v in overrides.items()}
    return {c: Rating(rating=v, rationale="r") for c, v in values.items()}


def test_bounds() -> None:
    assert compute_score({c: Rating(rating=1, rationale="r") for c in Criterion}) == 0
    assert compute_score({c: Rating(rating=5, rationale="r") for c in Criterion}) == 100
    assert compute_score(ratings()) == 50


def test_weights_matter() -> None:
    # pain (30) moves the score more than segment size (10)
    assert compute_score(ratings(pain_likelihood=5)) - 50 == 15
    assert compute_score(ratings(segment_size=5)) - 50 == 5


def test_missing_criterion_rejected() -> None:
    partial = ratings()
    del partial[Criterion.REACHABILITY]
    with pytest.raises(ValueError, match="reachability"):
        compute_score(partial)


def test_rating_range_validated() -> None:
    with pytest.raises(ValidationError):
        Rating(rating=6, rationale="r")
    with pytest.raises(ValidationError):
        Rating(rating=0, rationale="r")


def test_prompt_lists_every_criterion() -> None:
    text = rubric_prompt_lines()
    assert all(c.value in text for c in Criterion)
