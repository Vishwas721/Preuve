import uuid
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.research import service
from app.search.fetch import FetchedPage
from tests.conftest import FakeQueue
from tests.research_fixtures import claim, evidence_item, pack

PAGE = "Our project coordinators spend most of Friday compiling weekly progress reports."


class OnePageFetcher:
    async def fetch(self, url: str) -> FetchedPage:
        return FetchedPage(
            url=url,
            final_url=url,
            status_code=200,
            fetched_at=datetime.now(UTC),
            title="Forum thread",
            text=PAGE,
            full_text=PAGE,
            content_hash="0" * 64,
        )


async def new_idea(client: AsyncClient) -> str:
    body = {"title": "Construction AI", "description": "d", "target_market": "US"}
    return (await client.post("/ideas", json=body)).json()["id"]


async def test_import_enqueues_job(client: AsyncClient, queue: FakeQueue) -> None:
    idea_id = await new_idea(client)
    resp = await client.post(f"/ideas/{idea_id}/research-imports", json=pack(idea_id))
    assert resp.status_code == 202
    imp = resp.json()
    assert (imp["status"], imp["method_version"], imp["researcher"]) == (
        "queued",
        "1",
        "claude-code",
    )
    assert queue.jobs == [("verify_research_import", (imp["id"],))]


async def test_invalid_packs_get_precise_422s(client: AsyncClient) -> None:
    idea_id = await new_idea(client)
    url = f"/ideas/{idea_id}/research-imports"

    bad_schema = pack(idea_id, [evidence_item(quote="short")])
    resp = await client.post(url, json=bad_schema)
    assert resp.status_code == 422
    assert any("quote" in str(err["loc"]) for err in resp.json()["detail"])

    wrong_idea = pack(uuid.uuid4())
    resp = await client.post(url, json=wrong_idea)
    assert resp.status_code == 422 and "does not match" in resp.json()["detail"][0]

    missing_unknown = pack(idea_id, [evidence_item(unknown_ids=[str(uuid.uuid4())])])
    resp = await client.post(url, json=missing_unknown)
    assert resp.status_code == 422 and "unknown ids" in resp.json()["detail"][0]


async def test_queue_down_returns_503(client: AsyncClient, queue: FakeQueue) -> None:
    idea_id = await new_idea(client)
    queue.fail = True
    resp = await client.post(f"/ideas/{idea_id}/research-imports", json=pack(idea_id))
    assert resp.status_code == 503
    imports = (await client.get(f"/ideas/{idea_id}/research-imports")).json()
    assert imports[0]["status"] == "failed"


async def test_full_flow_and_evidence_edits(
    client: AsyncClient, session_maker: async_sessionmaker[AsyncSession]
) -> None:
    idea_id = await new_idea(client)
    unknown = (
        await client.post(f"/ideas/{idea_id}/unknowns", json={"question": "How often?"})
    ).json()
    body = pack(
        idea_id,
        [
            evidence_item(
                "ev-01",
                quote="spend most of Friday compiling weekly progress reports",
                unknown_ids=[unknown["id"]],
            ),
            evidence_item(
                "ev-02", url="https://example.com/other", quote="not on the page at all!"
            ),
        ],
        unknown_findings=[
            {
                "unknown_id": unknown["id"],
                "status": "answered",
                "summary": [claim("Weekly", "ev-01")],
            }
        ],
    )
    import_id = (await client.post(f"/ideas/{idea_id}/research-imports", json=body)).json()["id"]
    async with session_maker() as s:  # what the worker does
        await service.verify_import(s, OnePageFetcher(), uuid.UUID(import_id), delay=0)

    research = (await client.get(f"/ideas/{idea_id}/research")).json()
    assert research["imports"][0]["status"] == "done"
    assert research["imports"][0]["report"]["counts"] == {
        "verified": 1,
        "unverifiable": 0,
        "rejected": 1,
    }
    [ev] = research["evidence"]
    assert ev["verification"] == "verified" and ev["title"] == "Forum thread"
    assert ev["unknown_ids"] == [unknown["id"]]
    [finding] = research["findings"]
    assert finding["status"] == "answered"
    assert finding["summary"][0]["evidence_ids"] == [ev["id"]]

    filtered = await client.get(
        f"/ideas/{idea_id}/evidence", params={"unknown_id": unknown["id"], "stance": "supports"}
    )
    assert [e["id"] for e in filtered.json()] == [ev["id"]]
    none = await client.get(f"/ideas/{idea_id}/evidence", params={"stance": "contradicts"})
    assert none.json() == []

    patched = await client.patch(
        f"/ideas/{idea_id}/evidence/{ev['id']}", json={"stance": "neutral"}
    )
    assert (
        patched.json()["user_edited"] and patched.json()["original_labels"]["stance"] == "supports"
    )
    await client.patch(f"/ideas/{idea_id}/evidence/{ev['id']}", json={"dismissed": True})
    assert (await client.get(f"/ideas/{idea_id}/research")).json()["evidence"] == []

    one = await client.get(f"/ideas/{idea_id}/research-imports/{import_id}")
    assert one.json()["report"]["rejected"][0]["ref"] == "ev-02"


async def test_404s(client: AsyncClient) -> None:
    idea_id = await new_idea(client)
    missing = uuid.uuid4()
    assert (await client.get(f"/ideas/{idea_id}/research-imports/{missing}")).status_code == 404
    assert (
        await client.patch(f"/ideas/{idea_id}/evidence/{missing}", json={"dismissed": True})
    ).status_code == 404
    assert (await client.get(f"/ideas/{missing}/research")).status_code == 404
