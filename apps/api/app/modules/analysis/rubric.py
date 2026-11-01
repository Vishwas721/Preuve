"""ICP hypothesis-score rubric (Phase 1A decision 2).

The model rates each criterion 1–5 with a rationale; the 0–100 total is computed here, in code,
so scores are explainable and comparable across ideas and runs.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class Criterion(StrEnum):
    PAIN_LIKELIHOOD = "pain_likelihood"
    ABILITY_TO_PAY = "ability_to_pay"
    REACHABILITY = "reachability"
    FREQUENCY_URGENCY = "frequency_urgency"
    SEGMENT_SIZE = "segment_size"


WEIGHTS: dict[Criterion, int] = {
    Criterion.PAIN_LIKELIHOOD: 30,
    Criterion.ABILITY_TO_PAY: 25,
    Criterion.REACHABILITY: 20,
    Criterion.FREQUENCY_URGENCY: 15,
    Criterion.SEGMENT_SIZE: 10,
}
assert sum(WEIGHTS.values()) == 100

QUESTIONS: dict[Criterion, str] = {
    Criterion.PAIN_LIKELIHOOD: "How likely is this segment to feel the problem strongly?",
    Criterion.ABILITY_TO_PAY: "Does this segment plausibly have budget and buying authority?",
    Criterion.REACHABILITY: (
        "Can these companies and roles be found and contacted from public information?"
    ),
    Criterion.FREQUENCY_URGENCY: "How often, or how urgently, does the problem occur for them?",
    Criterion.SEGMENT_SIZE: "Are there enough such companies in the target market?",
}


class Rating(BaseModel):
    rating: int = Field(ge=1, le=5)
    rationale: str = Field(min_length=1)


def compute_score(ratings: dict[Criterion, Rating]) -> int:
    """Weighted 0–100: all 1s -> 0, all 5s -> 100."""
    missing = set(Criterion) - set(ratings)
    if missing:
        raise ValueError(f"Missing ratings for: {sorted(missing)}")
    total = sum(WEIGHTS[c] * (ratings[c].rating - 1) / 4 for c in Criterion)
    return round(total)


def rubric_prompt_lines() -> str:
    """Criterion definitions for prompts, so the model rates what the code weights."""
    return "\n".join(f"- {c.value}: {QUESTIONS[c]}" for c in Criterion)
