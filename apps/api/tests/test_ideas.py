from httpx import AsyncClient

IDEA = {
    "title": "Construction AI",
    "description": "AI tool that automates construction progress reports.",
    "target_market": "United States",
    "why_it_matters": "Project managers spend too much time creating reports.",
}


async def test_create_and_list(client: AsyncClient) -> None:
    resp = await client.post("/ideas", json=IDEA)
    assert resp.status_code == 201
    created = resp.json()
    assert created["state"] == "unvalidated"
    assert created["title"] == IDEA["title"]

    listed = (await client.get("/ideas")).json()
    assert [i["id"] for i in listed] == [created["id"]]


async def test_get_update_delete(client: AsyncClient) -> None:
    idea_id = (await client.post("/ideas", json=IDEA)).json()["id"]

    resp = await client.patch(f"/ideas/{idea_id}", json={"industry": "Construction"})
    assert resp.status_code == 200
    assert resp.json()["industry"] == "Construction"
    assert resp.json()["title"] == IDEA["title"]

    assert (await client.get(f"/ideas/{idea_id}")).json()["industry"] == "Construction"
    assert (await client.delete(f"/ideas/{idea_id}")).status_code == 204
    assert (await client.get(f"/ideas/{idea_id}")).status_code == 404


async def test_validation_errors(client: AsyncClient) -> None:
    assert (await client.post("/ideas", json={**IDEA, "title": ""})).status_code == 422
    assert (await client.post("/ideas", json={"title": "Missing fields"})).status_code == 422


async def test_unknown_idea_404(client: AsyncClient) -> None:
    resp = await client.get("/ideas/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
