import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.competitors import service as competitors
from app.modules.competitors.models import CompetitorStatus
from app.modules.competitors.schemas import CompetitorUpdate
from app.modules.ideas.models import Idea
from app.modules.ideas.schemas import IdeaCreate
from app.modules.ideas.service import create_idea
from app.modules.research import service as research
from app.modules.users.service import get_or_create_user
from app.search.fetch import FetchError
from tests.research_fixtures import claim, evidence_item, pack
from tests.test_research_service import FakeFetcher, run_import

PROCORE_PAGE = "Procore drafts your daily logs for final human verification. Pricing on request."
SHEETS_PAGE = "More than two-fifths use spreadsheets over software for project management."


def comp(ref: str, name: str, refs: list[str], **overrides) -> dict:
    return {
        "ref": ref,
        "name": name,
        "url": None,
        "kind": "direct",
        "description": f"{name} description",
        "evidence_refs": refs,
        "sentiment": [],
    } | overrides


def body(idea_id, competitors_list, current=None, extra_evidence=None) -> dict:
    evidence = [
        evidence_item(
            "ev-01",
            url="https://procore.com/a",
            quote="drafts your daily logs for final human verification",
        ),
        evidence_item(
            "ev-02",
            url="https://bdc.com/b",
            quote="more than two-fifths use spreadsheets over software",
        ),
        evidence_item(
            "ev-03", url="https://bdc.com/b", quote="this sentence does not exist on that page"
        ),
    ] + (extra_evidence or [])
    return pack(
        idea_id,
        evidence,
        competitors=competitors_list,
        current_solutions=current or [],
    )


FETCHER_PAGES = {"https://procore.com/a": PROCORE_PAGE, "https://bdc.com/b": SHEETS_PAGE}


@pytest.fixture
async def idea(session: AsyncSession) -> Idea:
    user = await get_or_create_user(session, "c@preuve.local", "C")
    return await create_idea(
        session, user.id, IdeaCreate(title="t", description="d", target_market="US")
    )


async def test_import_stores_verified_competitors_and_summary(
    session: AsyncSession, idea: Idea
) -> None:
    b = body(
        idea.id,
        [
            comp(
                "comp-01",
                "Procore",
                ["ev-01"],
                url="https://www.procore.com",
                sentiment=[claim("Drafts logs for review", "ev-01"), claim("Bad", "ev-03")],
            ),
            comp("comp-02", "Spreadsheets", ["ev-02"], kind="manual"),
            comp("comp-03", "Ghost Inc", ["ev-03"]),  # only cites rejected evidence
        ],
        current=[claim("Procore and spreadsheets", "ev-01", "ev-02"), claim("Bad", "ev-03")],
    )
    imp = await run_import(session, idea, b, FakeFetcher(FETCHER_PAGES))

    report = imp.report["competitors"]
    assert sorted(report["created"]) == ["Procore", "Spreadsheets"]
    assert report["rejected"] == [
        {"ref": "comp-03", "name": "Ghost Inc", "reason": "none of its evidence was stored"}
    ]
    assert {d.get("competitor") for d in imp.report["dropped_claims"]} >= {"Procore"}

    rows = {r["name"]: r for r in await competitors.list_competitors(session, idea.id)}
    assert set(rows) == {"Procore", "Spreadsheets"}
    assert rows["Procore"]["source"] == "research" and len(rows["Procore"]["evidence_ids"]) == 1
    assert [c["statement"] for c in rows["Procore"]["sentiment"]] == ["Drafts logs for review"]
    assert rows["Spreadsheets"]["kind"] == "manual"

    summary = await research.current_solutions(session, idea.id)
    assert [c["statement"] for c in summary] == ["Procore and spreadsheets"]
    assert len(summary[0]["evidence_ids"]) == 2


async def test_unverifiable_evidence_still_supports_a_competitor(
    session: AsyncSession, idea: Idea
) -> None:
    b = body(idea.id, [comp("comp-01", "Procore", ["ev-01"])])
    pages = FETCHER_PAGES | {"https://procore.com/a": FetchError("HTTP 403")}
    await run_import(session, idea, b, FakeFetcher(pages))
    [row] = await competitors.list_competitors(session, idea.id)
    assert row["name"] == "Procore" and len(row["evidence_ids"]) == 1


async def test_reimport_merges_and_respects_user_edits(session: AsyncSession, idea: Idea) -> None:
    await run_import(
        session,
        idea,
        body(idea.id, [comp("comp-01", "Procore", ["ev-01"])]),
        FakeFetcher(FETCHER_PAGES),
    )
    [row] = await competitors.list_competitors(session, idea.id)
    c = await competitors.get_competitor(session, idea.id, row["id"])
    await competitors.update_competitor(session, c, CompetitorUpdate(description="My own words"))

    second = body(
        idea.id,
        [comp("comp-09", "  PROCORE ", ["ev-01", "ev-02"], description="new research text")],
    )
    imp = await run_import(session, idea, second, FakeFetcher(FETCHER_PAGES))
    assert imp.report["competitors"]["updated"] == ["Procore"]

    [row] = await competitors.list_competitors(session, idea.id)
    assert row["description"] == "My own words"  # user edit kept
    assert len(row["evidence_ids"]) == 2  # evidence links merged


async def test_dismissed_competitor_stays_dismissed(session: AsyncSession, idea: Idea) -> None:
    b = body(idea.id, [comp("comp-01", "Procore", ["ev-01"])])
    await run_import(session, idea, b, FakeFetcher(FETCHER_PAGES))
    [row] = await competitors.list_competitors(session, idea.id)
    c = await competitors.get_competitor(session, idea.id, row["id"])
    await competitors.update_competitor(session, c, CompetitorUpdate(status="dismissed"))

    await run_import(session, idea, b, FakeFetcher(FETCHER_PAGES))
    assert await competitors.list_competitors(session, idea.id) == []
    [hidden] = await competitors.list_competitors(session, idea.id, include_dismissed=True)
    assert hidden["status"] == CompetitorStatus.DISMISSED


async def test_no_summary_means_empty(session: AsyncSession, idea: Idea) -> None:
    await run_import(session, idea, body(idea.id, []), FakeFetcher(FETCHER_PAGES))
    assert await research.current_solutions(session, idea.id) == []


# ---------- API ----------


async def new_idea(client: AsyncClient) -> str:
    return (
        await client.post("/ideas", json={"title": "t", "description": "d", "target_market": "US"})
    ).json()["id"]


async def test_manual_competitor_crud(client: AsyncClient) -> None:
    idea_id = await new_idea(client)
    base = f"/ideas/{idea_id}/competitors"
    payload = {"name": "WhatsApp groups", "kind": "manual", "description": "Photos shared in chats"}

    created = (await client.post(base, json=payload)).json()
    assert (created["source"], created["user_edited"], created["evidence_ids"]) == (
        "user",
        True,
        [],
    )
    assert (await client.post(base, json=payload | {"name": " whatsapp GROUPS"})).status_code == 409
    assert (await client.post(base, json=payload | {"url": "ftp://x"})).status_code == 422

    patched = await client.patch(f"{base}/{created['id']}", json={"kind": "indirect"})
    assert patched.json()["kind"] == "indirect"
    await client.patch(f"{base}/{created['id']}", json={"status": "dismissed"})
    assert (await client.get(base)).json() == []
    assert len((await client.get(base, params={"include_dismissed": True})).json()) == 1
    assert (await client.patch(f"{base}/{uuid.uuid4()}", json={})).status_code == 404


async def test_research_read_includes_competitors(
    client: AsyncClient, session_maker: async_sessionmaker[AsyncSession]
) -> None:
    idea_id = await new_idea(client)
    await client.post(
        f"/ideas/{idea_id}/competitors",
        json={
            "name": "Consultants",
            "kind": "service",
            "description": "Owner's reps write reports",
        },
    )
    research_body = (await client.get(f"/ideas/{idea_id}/research")).json()
    assert [c["name"] for c in research_body["competitors"]] == ["Consultants"]
    assert research_body["current_solutions"] == []
