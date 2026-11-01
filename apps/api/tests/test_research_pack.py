import uuid

import pytest
from pydantic import ValidationError

from app.modules.research.pack import ResearchPack
from app.scripts.export_pack_schema import SCHEMA_PATH, render
from tests.research_fixtures import claim, evidence_item, pack

IDEA = uuid.uuid4()


def test_valid_pack() -> None:
    finding = {
        "unknown_id": str(uuid.uuid4()),
        "status": "answered",
        "summary": [claim("x", "ev-01")],
    }
    p = ResearchPack.model_validate(pack(IDEA, unknown_findings=[finding]))
    assert p.meta.schema_version == "1.0" and len(p.evidence) == 1


def test_schema_export_is_in_sync() -> None:
    assert SCHEMA_PATH.read_text(encoding="utf-8") == render(), (
        "Run: uv run python -m app.scripts.export_pack_schema"
    )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"quote": "too short"}, "at least 20"),
        ({"url": "ftp://example.com/x"}, "http(s)"),
        ({"kind": "assumption"}, "kind"),
        ({"ref": "Bad Ref!"}, "ref"),
    ],
)
def test_evidence_field_validation(overrides: dict, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        ResearchPack.model_validate(pack(IDEA, [evidence_item(**overrides)]))


def test_duplicate_refs_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate evidence refs"):
        ResearchPack.model_validate(pack(IDEA, [evidence_item("ev-01"), evidence_item("ev-01")]))


def test_claims_must_cite_known_refs() -> None:
    finding = {
        "unknown_id": str(uuid.uuid4()),
        "status": "answered",
        "summary": [claim("x", "ev-99")],
    }
    with pytest.raises(ValidationError, match="ev-99"):
        ResearchPack.model_validate(pack(IDEA, unknown_findings=[finding]))


def test_fact_claim_needs_evidence() -> None:
    finding = {"unknown_id": str(uuid.uuid4()), "status": "answered", "summary": [claim("x")]}
    with pytest.raises(ValidationError, match="fact"):
        ResearchPack.model_validate(pack(IDEA, unknown_findings=[finding]))


def test_answered_finding_needs_summary_but_no_evidence_is_fine_empty() -> None:
    uid = str(uuid.uuid4())
    with pytest.raises(ValidationError, match="no summary"):
        ResearchPack.model_validate(
            pack(IDEA, unknown_findings=[{"unknown_id": uid, "status": "answered", "summary": []}])
        )
    ok = pack(IDEA, unknown_findings=[{"unknown_id": uid, "status": "no_evidence_found"}])
    assert ResearchPack.model_validate(ok).unknown_findings[0].summary == []


def test_hypothesis_update_needs_rationale() -> None:
    hyp = {
        "problem": "p",
        "users": "u",
        "buyer": "b",
        "decision_maker": "d",
        "economic_value": "e",
        "geography": "g",
        "industry": "i",
        "rationale": [],
    }
    with pytest.raises(ValidationError, match="rationale"):
        ResearchPack.model_validate(pack(IDEA, hypothesis_update=hyp))
