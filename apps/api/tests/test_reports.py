"""Validation reports (PRD §44): numbers from the snapshot, only cited summary claims."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.llm.base import LLMUnavailableError
from app.llm.fake import FakeProvider
from app.llm.router import LLMRouter
from app.llm.tasks import ProviderName
from app.modules.ideas.models import Idea
from app.modules.reports import service as reports
from app.modules.reports.models import ReportStatus
from app.modules.validation.models import ValidationScore
from tests.test_prospects import idea  # noqa: F401  (fixture)
from tests.test_responses import api_idea, llm_with
from tests.test_validation import _reply


def summary(*claims: dict) -> dict:
    return {"claims": list(claims)}


GOOD = {
    "statement": "1 customer confirmed the problem (E1).",
    "kind": "fact",
    "evidence_ids": ["E1"],
}
BAD = [
    {"statement": "17 prospects confirmed the problem.", "kind": "fact", "evidence_ids": ["E1"]},
    {
        "statement": "Construction firms all need this.",
        "kind": "inference",
        "evidence_ids": ["E99"],
    },
    {"statement": "The market is large.", "kind": "assumption", "evidence_ids": []},
    {"statement": "The reply sounds keen.", "kind": "inference", "evidence_ids": []},
]


def test_claim_checks() -> None:
    from app.llm.guardrails import Claim
    from app.modules.reports.prompts import check_claim, numbers

    allowed = {"1", "23"} | numbers("Our PMs spend about 4-5 hours creating reports")
    ok = Claim(statement="It takes 4-5 hours a week (E2).", kind="fact", evidence_ids=["E2"])
    assert check_claim(ok, {"E1", "E2"}, allowed) is None
    assert numbers("see E12 and E3") == set()
    rounded = Claim(statement="About 5.5 hours.", kind="fact", evidence_ids=["E2"])
    assert "5.5" in check_claim(rounded, {"E2"}, allowed)


async def _report(session: AsyncSession, idea: Idea, *responses_):
    await _reply(session, idea)
    row = await reports.create(session, idea)
    llm, local, gemini = llm_with(*responses_)
    assert await reports.generate(session, llm, row.id) == ReportStatus.DONE
    await session.refresh(row)
    return row, local, gemini


async def test_report_keeps_only_cited_claims_with_known_numbers(
    session: AsyncSession, idea: Idea
) -> None:
    row, local, gemini = await _report(session, idea, summary(GOOD, *BAD))
    # private: reply quotes go to the local model only
    assert local.calls and not gemini.calls
    assert "E1 [reply" in local.calls[0].prompt

    assert [c["statement"] for c in row.summary] == [GOOD["statement"]]
    reasons = {d["statement"]: d["reason"] for d in row.dropped}
    assert "numbers not in the score record: 17" in reasons[BAD[0]["statement"]]
    assert "unknown exhibits E99" in reasons[BAD[1]["statement"]]
    assert reasons[BAD[2]["statement"]].startswith("assumption")
    assert reasons[BAD[3]["statement"]] == "cites no exhibit"
    assert GOOD["statement"] in row.content and "17 prospects" not in row.content
    assert row.summary_provider == "local"


async def test_report_numbers_match_the_score_record(session: AsyncSession, idea: Idea) -> None:
    row, _, _ = await _report(session, idea, summary())
    score = await session.get(ValidationScore, row.validation_score_id)
    md = row.content
    assert f"Score: **{score.total}/100**" in md
    assert score.decision["headline"] in md and "Don't build yet" in md
    assert "INVESTIGATE FURTHER" in md
    for d in score.dimensions:
        assert f"| {d['label']} | {d['points']}/{d['max']} |" in md
    f = score.facts
    assert f"{f['confirming_customers']} customers confirmed" in md
    assert f"{f['validated_conversations']} validated customer conversations" in md
    for p in score.decision["weak"]:
        assert p["text"] in md
    for a in score.decision["next_actions"]:
        assert a in md
    # every exhibit has its quote, source and fetched date
    assert row.exhibits and all(ref in md for ref in row.exhibits.values())
    assert "preuve://responses/" in md and "fetched 20" in md
    assert reports.NO_SUMMARY in md  # the summary was empty


async def test_summary_failure_still_produces_the_report(session: AsyncSession, idea: Idea) -> None:
    row, _, _ = await _report(session, idea, LLMUnavailableError("ollama down"))
    assert row.status == ReportStatus.DONE
    assert reports.NO_SUMMARY in row.content and row.summary == []
    assert "Summary unavailable" in row.dropped[0]["reason"]


async def test_no_evidence_means_no_model_call(session: AsyncSession, idea: Idea) -> None:
    row = await reports.create(session, idea)
    llm, local, gemini = llm_with()
    await reports.generate(session, llm, row.id)
    await session.refresh(row)
    assert not local.calls and not gemini.calls
    assert "## Exhibits\n\nNo evidence found." in row.content
    assert "Weak evidence. Don't build yet." in row.content


async def test_private_summary_goes_to_gemini_only_when_allowed(
    session: AsyncSession, idea: Idea
) -> None:
    await _reply(session, idea)
    row = await reports.create(session, idea)
    local, gemini = FakeProvider("local"), FakeProvider("gemini", [summary(GOOD)])
    llm = LLMRouter(
        {ProviderName.LOCAL: local, ProviderName.GEMINI: gemini}, allow_private_remote=True
    )
    await reports.generate(session, llm, row.id)
    await session.refresh(row)
    assert gemini.calls and not local.calls and row.summary_provider == "gemini"


async def test_report_reuses_a_fresh_snapshot_and_recomputes_a_stale_one(
    session: AsyncSession, idea: Idea
) -> None:
    first = await reports.create(session, idea)
    again = await reports.create(session, idea)
    assert again.validation_score_id == first.validation_score_id
    await _reply(session, idea)  # data changed
    third = await reports.create(session, idea)
    assert third.validation_score_id != first.validation_score_id


async def test_reports_api(
    client: AsyncClient, session_maker: async_sessionmaker[AsyncSession], queue
) -> None:
    idea = await api_idea(client, session_maker)
    created = await client.post(f"/ideas/{idea.id}/reports")
    assert created.status_code == 201, created.text
    rid = created.json()["id"]
    assert queue.jobs[-1] == ("validation_report", (rid,))
    assert created.json()["status"] == "queued" and created.json()["total"] == 0

    assert (await client.get(f"/reports/{rid}/markdown")).status_code == 409
    async with session_maker() as session:
        llm, _, _ = llm_with()
        await reports.generate(session, llm, uuid.UUID(rid))

    body = (await client.get(f"/reports/{rid}")).json()
    assert body["status"] == "done" and body["content"].startswith("# Validation report: t")
    md = await client.get(f"/reports/{rid}/markdown")
    assert md.status_code == 200 and md.headers["content-type"].startswith("text/markdown")
    assert 'filename="preuve-t-' in md.headers["content-disposition"]
    assert md.text == body["content"]

    assert [r["id"] for r in (await client.get(f"/ideas/{idea.id}/reports")).json()] == [rid]
    assert (await client.delete(f"/reports/{rid}")).status_code == 204
    assert (await client.get(f"/reports/{rid}")).status_code == 404
    assert (await client.get(f"/reports/{uuid.uuid4()}")).status_code == 404
