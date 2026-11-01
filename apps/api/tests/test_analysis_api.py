import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.analysis import service
from tests.analysis_fixtures import analysis_output, icp, icps_output, make_router, ratings
from tests.conftest import FakeQueue

IDEA = {
    "title": "Construction AI",
    "description": "AI tool that automates construction progress reports.",
    "target_market": "United States",
}


async def new_idea(client: AsyncClient) -> str:
    return (await client.post("/ideas", json=IDEA)).json()["id"]


async def run_worker(session_maker: async_sessionmaker[AsyncSession], run_id: str) -> None:
    """Do what the arq worker would do, with canned LLM output."""
    router, _, gemini = make_router()
    gemini.queue(analysis_output(), icps_output(icp("Mid-size GCs", pain=5), icp("Small GCs")))
    async with session_maker() as s:
        await service.execute_run(s, router, uuid.UUID(run_id))


async def test_empty_analysis(client: AsyncClient) -> None:
    idea_id = await new_idea(client)
    body = (await client.get(f"/ideas/{idea_id}/analysis")).json()
    assert body == {"hypothesis": None, "unknowns": [], "icps": [], "latest_run": None}


async def test_analyze_enqueues_and_blocks_concurrent_runs(
    client: AsyncClient, queue: FakeQueue
) -> None:
    idea_id = await new_idea(client)
    resp = await client.post(f"/ideas/{idea_id}/analyze")
    assert resp.status_code == 202
    run = resp.json()
    assert (run["status"], run["kind"]) == ("queued", "full")
    assert queue.jobs == [("run_analysis", (run["id"],))]

    assert (await client.post(f"/ideas/{idea_id}/analyze")).status_code == 409
    got = await client.get(f"/ideas/{idea_id}/analysis-runs/{run['id']}")
    assert got.json()["status"] == "queued"


async def test_queue_down_returns_503_and_frees_the_idea(
    client: AsyncClient, queue: FakeQueue
) -> None:
    idea_id = await new_idea(client)
    queue.fail = True
    assert (await client.post(f"/ideas/{idea_id}/analyze")).status_code == 503
    latest = (await client.get(f"/ideas/{idea_id}/analysis")).json()["latest_run"]
    assert latest["status"] == "failed"
    queue.fail = False
    assert (await client.post(f"/ideas/{idea_id}/analyze")).status_code == 202


async def test_generate_icps_needs_hypothesis(client: AsyncClient) -> None:
    idea_id = await new_idea(client)
    resp = await client.post(f"/ideas/{idea_id}/icps/generate")
    assert resp.status_code == 409
    assert "Analyze" in resp.json()["detail"]


async def test_full_flow(
    client: AsyncClient, session_maker: async_sessionmaker[AsyncSession]
) -> None:
    idea_id = await new_idea(client)
    run_id = (await client.post(f"/ideas/{idea_id}/analyze")).json()["id"]
    await run_worker(session_maker, run_id)

    body = (await client.get(f"/ideas/{idea_id}/analysis")).json()
    assert body["latest_run"]["status"] == "succeeded"
    assert body["hypothesis"]["version"] == 1 and body["hypothesis"]["source"] == "ai"
    assert len(body["unknowns"]) == 3
    top = body["icps"][0]
    assert top["name"] == "Mid-size GCs" and top["is_primary"]
    breakdown = {c["criterion"]: c for c in top["score_breakdown"]}
    assert breakdown["pain_likelihood"] == {
        "criterion": "pain_likelihood",
        "weight": 30,
        "rating": 5,
        "rationale": "rated 5",
        "points": 30.0,
    }
    assert abs(sum(c["points"] for c in top["score_breakdown"]) - top["hypothesis_score"]) <= 0.5


async def test_edit_endpoints(
    client: AsyncClient, session_maker: async_sessionmaker[AsyncSession]
) -> None:
    idea_id = await new_idea(client)
    run_id = (await client.post(f"/ideas/{idea_id}/analyze")).json()["id"]
    await run_worker(session_maker, run_id)
    base = f"/ideas/{idea_id}"

    # hypothesis: new version on edit
    edit = analysis_output("Sharper problem")["hypothesis"] | {"change_note": "sharper"}
    assert (await client.post(f"{base}/hypothesis", json=edit)).json()["version"] == 2
    versions = (await client.get(f"{base}/hypothesis/versions")).json()
    assert [v["version"] for v in versions] == [2, 1]

    # unknowns: add, edit, drop
    u = (await client.post(f"{base}/unknowns", json={"question": "Who signs off?"})).json()
    assert u["source"] == "user" and u["category"] == "other"
    resp = await client.patch(f"{base}/unknowns/{u['id']}", json={"status": "dropped"})
    assert resp.json()["status"] == "dropped"
    assert len((await client.get(f"{base}/unknowns")).json()) == 3
    all_unknowns = (await client.get(f"{base}/unknowns?include_dropped=true")).json()
    assert len(all_unknowns) == 4

    # ICPs: create as primary, rescore, dismiss
    new_icp = {
        "name": "Specialty",
        "company_type": "Specialty contractors",
        "geography": "US",
        "ratings": ratings(),
        "is_primary": True,
    }
    created = (await client.post(f"{base}/icps", json=new_icp)).json()
    assert created["hypothesis_score"] == 50 and created["is_primary"]
    icps = (await client.get(f"{base}/icps")).json()
    assert [i["is_primary"] for i in icps].count(True) == 1

    patched = await client.patch(
        f"{base}/icps/{created['id']}", json={"ratings": ratings(5, 5, 5, 5, 5)}
    )
    assert patched.json()["hypothesis_score"] == 100
    dismissed = await client.patch(f"{base}/icps/{created['id']}", json={"status": "dismissed"})
    assert dismissed.json()["is_primary"] is False
    assert len((await client.get(f"{base}/icps")).json()) == 2


async def test_validation_and_404s(client: AsyncClient) -> None:
    idea_id = await new_idea(client)
    base = f"/ideas/{idea_id}"
    bad_rating = {
        "name": "X",
        "company_type": "Y",
        "geography": "US",
        "ratings": ratings(pain=6),
    }
    assert (await client.post(f"{base}/icps", json=bad_rating)).status_code == 422
    assert (await client.post(f"{base}/unknowns", json={"question": ""})).status_code == 422

    missing = uuid.uuid4()
    assert (await client.patch(f"{base}/unknowns/{missing}", json={})).status_code == 404
    assert (await client.patch(f"{base}/icps/{missing}", json={})).status_code == 404
    assert (await client.get(f"{base}/analysis-runs/{missing}")).status_code == 404
    assert (await client.get(f"/ideas/{missing}/analysis")).status_code == 404
