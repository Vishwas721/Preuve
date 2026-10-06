import pytest
from pydantic import BaseModel, ValidationError

from app.llm.base import LLMOutputError, parse_structured
from app.llm.guardrails import Claim, ClaimKind, UngroundedClaimError, verify_citations


def test_fact_requires_evidence() -> None:
    with pytest.raises(ValidationError):
        Claim(statement="PMs spend 4h/week on reports", kind=ClaimKind.FACT)


def test_fact_with_evidence_ok() -> None:
    claim = Claim(statement="Job post mentions weekly reports", kind="fact", evidence_ids=["e1"])
    assert claim.kind == ClaimKind.FACT


def test_assumption_without_evidence_ok() -> None:
    assert Claim(statement="Probably common", kind="assumption").evidence_ids == []


def test_verify_citations_rejects_unknown_ids() -> None:
    claims = [Claim(statement="x", kind="fact", evidence_ids=["e1", "e9"])]
    with pytest.raises(UngroundedClaimError, match="e9"):
        verify_citations(claims, {"e1", "e2"})


def test_verify_citations_accepts_known_ids() -> None:
    claims = [Claim(statement="x", kind="inference", evidence_ids=["e1"])]
    assert verify_citations(claims, ["e1"]) == claims


def test_ungrounded_is_an_output_error() -> None:
    # So callers can treat hallucinated citations like any other invalid output.
    assert issubclass(UngroundedClaimError, LLMOutputError)


class Item(BaseModel):
    n: int


def test_parse_structured_accepts_code_fence() -> None:
    assert parse_structured('```json\n{"n": 3}\n```', Item).n == 3


def test_parse_structured_rejects_bad_output() -> None:
    with pytest.raises(LLMOutputError):
        parse_structured("Sure! Here it is: {n: 3}", Item)
