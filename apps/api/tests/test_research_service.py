from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analysis import service as analysis
from app.modules.analysis.models import Source
from app.modules.analysis.schemas import UnknownCreate
from app.modules.ideas.models import Idea
from app.modules.ideas.schemas import IdeaCreate
from app.modules.ideas.service import create_idea
from app.modules.research import service
from app.modules.research.models import (
    EvidenceUnknown,
    FetchStatus,
    ImportStatus,
    ResearchImport,
    WebSource,
)
from app.modules.research.pack import ResearchPack
from app.modules.research.schemas import EvidenceUpdate
from app.modules.users.service import get_or_create_user
from app.modules.workspaces.service import personal_workspace_id
from app.search.fetch import FetchedPage, FetchError
from tests.research_fixtures import claim, evidence_item, pack

PAGE_A = (
    "Weekly reports are painful. Our project coordinators spend most of Friday compiling weekly "
    "progress reports from site photos and emails. It is entirely manual."
)
PAGE_B = "We switched tools last year and reporting now takes ten minutes per project."


class FakeFetcher:
    def __init__(self, pages: dict[str, str | Exception], full: dict[str, str] | None = None):
        self.pages = pages
        self.full = full or {}
        self.calls: list[str] = []

    async def fetch(self, url: str) -> FetchedPage:
        self.calls.append(url)
        page = self.pages[url]
        if isinstance(page, Exception):
            raise page
        return FetchedPage(
            url=url,
            final_url=url,
            status_code=200,
            fetched_at=datetime.now(UTC),
            title="Title",
            text=page,
            full_text=self.full.get(url, page),
            content_hash="0" * 64,
        )


@pytest.fixture
async def idea(session: AsyncSession) -> Idea:
    user = await get_or_create_user(session, "r@preuve.local", "R")
    return await create_idea(
        session,
        await personal_workspace_id(session, user),
        IdeaCreate(title="t", description="d", target_market="US"),
    )


async def run_import(
    session: AsyncSession, idea: Idea, body: dict, fetcher: FakeFetcher
) -> ResearchImport:
    p = ResearchPack.model_validate(body)
    assert await service.validate_for_idea(session, idea, p) == []
    imp = await service.create_import(session, idea, p)
    await service.verify_import(session, fetcher, imp.id, delay=0)
    await session.refresh(imp)
    return imp


async def test_verified_unverifiable_and_rejected(session: AsyncSession, idea: Idea) -> None:
    fetcher = FakeFetcher(
        {
            "https://a.com/1": PAGE_A,
            "https://reddit.com/x": FetchError("Disallowed by robots.txt"),
            "https://b.com/2": PAGE_B,
        }
    )
    body = pack(
        idea.id,
        [
            evidence_item(
                "ev-01",
                url="https://a.com/1",
                quote="spend most of Friday compiling weekly progress reports",
            ),
            evidence_item(
                "ev-02",
                url="https://reddit.com/x",
                quote="reports eat every single Friday afternoon",
            ),
            evidence_item(
                "ev-03", url="https://b.com/2", quote="reporting takes four hours per project"
            ),
        ],
    )
    imp = await run_import(session, idea, body, fetcher)
    assert imp.status == ImportStatus.DONE
    assert imp.report["counts"] == {"verified": 1, "unverifiable": 1, "rejected": 1}
    assert imp.report["rejected"] == [
        {"ref": "ev-03", "url": "https://b.com/2", "reason": "quote not found on page"}
    ]

    evidence = {e["ref"]: e for e in await service.list_evidence(session, idea.id)}
    assert set(evidence) == {"ev-01", "ev-02"}
    assert evidence["ev-01"]["verification"] == "verified"
    assert evidence["ev-02"]["verification"] == "unverifiable"
    assert "robots" in evidence["ev-02"]["verification_note"]

    sources = {s.url: s for s in await session.scalars(select(WebSource))}
    assert sources["https://a.com/1"].fetch_status == FetchStatus.OK
    assert sources["https://a.com/1"].full_text == PAGE_A
    assert sources["https://reddit.com/x"].fetch_status == FetchStatus.FAILED


async def test_each_url_fetched_once(session: AsyncSession, idea: Idea) -> None:
    fetcher = FakeFetcher({"https://a.com/1": PAGE_A})
    body = pack(
        idea.id,
        [
            evidence_item(
                "ev-01", url="https://a.com/1", quote="spend most of Friday compiling weekly"
            ),
            evidence_item(
                "ev-02", url="https://a.com/1", quote="It is entirely manual and painful"[:20]
            ),
        ],
    )
    await run_import(session, idea, body, fetcher)
    assert fetcher.calls == ["https://a.com/1"]


async def test_full_text_fallback(session: AsyncSession, idea: Idea) -> None:
    fetcher = FakeFetcher(
        {"https://a.com/1": "Main article only."},
        full={"https://a.com/1": "Main article only. Sidebar: we lose hours to weekly reports."},
    )
    body = pack(
        idea.id, [evidence_item(url="https://a.com/1", quote="we lose hours to weekly reports")]
    )
    imp = await run_import(session, idea, body, fetcher)
    assert imp.report["counts"]["verified"] == 1


async def test_unexpected_fetch_error_is_unverifiable(session: AsyncSession, idea: Idea) -> None:
    fetcher = FakeFetcher({"https://a.com/1": RuntimeError("socket exploded")})
    imp = await run_import(
        session, idea, pack(idea.id, [evidence_item(url="https://a.com/1")]), fetcher
    )
    assert imp.status == ImportStatus.DONE
    assert imp.report["counts"]["unverifiable"] == 1


async def test_findings_drop_claims_on_rejected_evidence(session: AsyncSession, idea: Idea) -> None:
    u1 = await analysis.create_unknown(session, idea.id, UnknownCreate(question="How often?"))
    u2 = await analysis.create_unknown(session, idea.id, UnknownCreate(question="Who pays?"))
    fetcher = FakeFetcher({"https://a.com/1": PAGE_A, "https://b.com/2": PAGE_B})
    body = pack(
        idea.id,
        [
            evidence_item(
                "ev-01",
                url="https://a.com/1",
                quote="spend most of Friday compiling weekly",
                unknown_ids=[str(u1.id)],
            ),
            evidence_item(
                "ev-02", url="https://b.com/2", quote="this sentence is not on the page at all"
            ),
        ],
        unknown_findings=[
            {
                "unknown_id": str(u1.id),
                "status": "answered",
                "summary": [claim("Weekly", "ev-01"), claim("Bad", "ev-02")],
            },
            {
                "unknown_id": str(u2.id),
                "status": "partially_answered",
                "summary": [claim("Bad only", "ev-02")],
            },
        ],
    )
    imp = await run_import(session, idea, body, fetcher)

    findings = {f.unknown_id: f for f in await service.latest_findings(session, idea.id)}
    f1, f2 = findings[u1.id], findings[u2.id]
    assert f1.status == "answered" and [c["statement"] for c in f1.summary] == ["Weekly"]
    evidence_id = (await service.list_evidence(session, idea.id))[0]["id"]
    assert f1.summary[0]["evidence_ids"] == [str(evidence_id)]
    assert f2.status == "no_evidence_found" and f2.summary == []
    assert imp.report["downgraded_findings"] == [str(u2.id)]
    assert len(imp.report["dropped_claims"]) == 2

    links = list(await session.scalars(select(EvidenceUnknown)))
    assert [(link.evidence_id, link.unknown_id) for link in links] == [(evidence_id, u1.id)]


HYPOTHESIS = {
    "problem": "Coordinators lose Fridays to reports",
    "users": "Coordinators",
    "buyer": "Ops directors",
    "decision_maker": "Owner",
    "economic_value": "A day a week",
    "geography": "US",
    "industry": "Construction",
}


async def test_hypothesis_update_and_new_unknowns(session: AsyncSession, idea: Idea) -> None:
    fetcher = FakeFetcher({"https://a.com/1": PAGE_A})
    body = pack(
        idea.id,
        [
            evidence_item(
                "ev-01", url="https://a.com/1", quote="spend most of Friday compiling weekly"
            )
        ],
        hypothesis_update=HYPOTHESIS | {"rationale": [claim("Fridays lost", "ev-01")]},
        new_unknowns=[{"question": "Do owners read the reports?", "priority": "high"}],
    )
    imp = await run_import(session, idea, body, fetcher)
    hyp = await analysis.get_current_hypothesis(session, idea.id)
    assert (hyp.version, hyp.source, imp.report["hypothesis_version"]) == (1, Source.RESEARCH, 1)
    assert "Fridays lost" in hyp.change_note
    unknowns = await analysis.list_unknowns(session, idea.id)
    assert [(u.question, u.source) for u in unknowns] == [
        ("Do owners read the reports?", Source.RESEARCH)
    ]


async def test_hypothesis_update_skipped_without_verified_rationale(
    session: AsyncSession, idea: Idea
) -> None:
    fetcher = FakeFetcher({"https://a.com/1": PAGE_A})
    body = pack(
        idea.id,
        [evidence_item("ev-01", url="https://a.com/1", quote="words that are not on this page")],
        hypothesis_update=HYPOTHESIS | {"rationale": [claim("x", "ev-01")]},
    )
    imp = await run_import(session, idea, body, fetcher)
    assert imp.report["hypothesis_version"] is None and imp.report["hypothesis_skipped"]
    assert await analysis.get_current_hypothesis(session, idea.id) is None


async def test_reimport_deduplicates_and_upgrades(session: AsyncSession, idea: Idea) -> None:
    item = evidence_item(url="https://a.com/1", quote="spend most of Friday compiling weekly")
    await run_import(
        session, idea, pack(idea.id, [item]), FakeFetcher({"https://a.com/1": FetchError("503")})
    )
    first = await service.list_evidence(session, idea.id)
    assert first[0]["verification"] == "unverifiable"

    imp2 = await run_import(
        session, idea, pack(idea.id, [item]), FakeFetcher({"https://a.com/1": PAGE_A})
    )
    after = await service.list_evidence(session, idea.id)
    assert len(after) == 1 and after[0]["verification"] == "verified"
    assert imp2.report["duplicates"] == ["ev-01"]


async def test_validate_for_idea(session: AsyncSession, idea: Idea) -> None:
    other = await create_idea(
        session, idea.workspace_id, IdeaCreate(title="o", description="d", target_market="US")
    )
    foreign = await analysis.create_unknown(session, other.id, UnknownCreate(question="Elsewhere?"))
    p = ResearchPack.model_validate(pack(other.id, [evidence_item(unknown_ids=[str(foreign.id)])]))
    errors = await service.validate_for_idea(session, idea, p)
    assert any("does not match" in e for e in errors)
    assert any(str(foreign.id) in e for e in errors)


async def test_evidence_edits_keep_original_labels(session: AsyncSession, idea: Idea) -> None:
    fetcher = FakeFetcher({"https://a.com/1": PAGE_A})
    await run_import(
        session,
        idea,
        pack(
            idea.id,
            [evidence_item(url="https://a.com/1", quote="spend most of Friday compiling weekly")],
        ),
        fetcher,
    )
    row = (await service.list_evidence(session, idea.id))[0]
    ev = await service.get_evidence(session, idea.id, row["id"])

    await service.update_evidence(session, ev, EvidenceUpdate(stance="neutral"))
    await service.update_evidence(session, ev, EvidenceUpdate(kind="inference"))
    assert ev.user_edited
    assert ev.original_labels == {"kind": "fact", "stance": "supports", "relevance": "high"}

    await service.update_evidence(session, ev, EvidenceUpdate(dismissed=True))
    assert await service.list_evidence(session, idea.id) == []
    assert len(await service.list_evidence(session, idea.id, include_dismissed=True)) == 1
