"""Builders for research tests."""

import uuid


def evidence_item(ref: str = "ev-01", **overrides) -> dict:
    item = {
        "ref": ref,
        "url": f"https://example.com/{ref}",
        "title": "Weekly reports are painful",
        "source_type": "forum",
        "quote": "Our project coordinators spend most of Friday compiling weekly progress reports",
        "statement": "Coordinators spend a day a week on reports.",
        "kind": "fact",
        "stance": "supports",
        "relevance": "high",
        "unknown_ids": [],
    }
    return item | overrides


def pack(idea_id: uuid.UUID | str, evidence: list[dict] | None = None, **overrides) -> dict:
    body = {
        "meta": {"method_version": "1", "idea_id": str(idea_id), "queries": ["q1"]},
        "evidence": evidence if evidence is not None else [evidence_item()],
        "unknown_findings": [],
        "hypothesis_update": None,
        "new_unknowns": [],
    }
    return body | overrides


def claim(statement: str, *refs: str, kind: str = "fact") -> dict:
    return {"statement": statement, "kind": kind, "evidence_ids": list(refs)}
