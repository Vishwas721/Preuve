import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.research import service as research
from tests.research_fixtures import evidence_item, pack
from tests.test_research_service import FakeFetcher

PAGE = "Our project coordinators spend most of Friday compiling weekly progress reports."


async def test_portfolio_aggregates(
    client: AsyncClient, session_maker: async_sessionmaker[AsyncSession]
) -> None:
    body = {"title": "Older", "description": "d", "target_market": "US"}
    older = (await client.post("/ideas", json=body)).json()["id"]
    newer = (await client.post("/ideas", json=body | {"title": "Newer"})).json()["id"]
    await client.post(f"/ideas/{newer}/unknowns", json={"question": "How often?"})
    await client.post(
        f"/ideas/{newer}/competitors",
        json={"name": "Sheets", "kind": "manual", "description": "Spreadsheets"},
    )

    items = [
        evidence_item(
            "ev-01", url="https://a.com/1", quote="spend most of Friday compiling weekly"
        ),
        evidence_item(
            "ev-02",
            url="https://b.com/2",
            quote="a quote from a blocked page here",
            stance="contradicts",
        ),
    ]
    imp = (await client.post(f"/ideas/{newer}/research-imports", json=pack(newer, items))).json()
    async with session_maker() as s:
        from app.search.fetch import FetchError

        fetcher = FakeFetcher({"https://a.com/1": PAGE, "https://b.com/2": FetchError("403")})
        await research.verify_import(s, fetcher, uuid.UUID(imp["id"]), delay=0)

    board = (await client.get("/portfolio")).json()
    assert [i["title"] for i in board] == ["Newer", "Older"]  # most recent activity first
    item = board[0]
    assert item["evidence"] == {
        "supports": 1,
        "contradicts": 1,
        "neutral": 0,
        "verified": 1,
        "unverifiable": 1,
    }
    assert (item["competitors"], item["prospects"], item["top_score"]) == (1, 0, None)
    assert (item["unknowns_open"], item["unknowns_answered"], item["busy"]) == (1, 0, False)
    assert board[1]["id"] == older and board[1]["problem"] is None


async def test_empty_portfolio(client: AsyncClient) -> None:
    assert (await client.get("/portfolio")).json() == []


async def test_portfolio_shows_latest_validation_and_funnel(client: AsyncClient) -> None:
    created = await client.post(
        "/ideas", json={"title": "Scored", "description": "d", "target_market": "US"}
    )
    iid = created.json()["id"]
    [item] = (await client.get("/portfolio")).json()
    assert item["validation"] is None
    assert item["funnel"] == {"sent": 0, "replies": 0, "interviews_done": 0, "pilot_or_better": 0}

    score = (await client.post(f"/ideas/{iid}/score")).json()
    [item] = (await client.get("/portfolio")).json()
    v = item["validation"]
    assert v["score"] == score["total"] == 0 and v["recommendation"] == "investigate"
    assert v["headline"] == "Weak evidence. Don't build yet." and v["stale"] is False
    assert v["validated_conversations"] == 0
