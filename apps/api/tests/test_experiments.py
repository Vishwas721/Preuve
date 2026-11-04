"""Experiments (PRD §28): cohorts over real outreach and reply data."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.experiments import service as experiments
from app.modules.experiments.schemas import Cohort, ExperimentCreate, ExperimentUpdate
from app.modules.ideas.models import Idea
from app.modules.responses import service as responses
from app.modules.responses.schemas import ResponsePaste
from tests.test_prospects import idea  # noqa: F401  (fixture)
from tests.test_responses import REPLY, api_idea, classification, llm_with, sent_message


async def _replied(session: AsyncSession, idea: Idea):
    message = await sent_message(session, idea)  # to Jane Roe, Project Engineer
    r = await responses.create_paste(
        session, idea, ResponsePaste(text=REPLY, message_id=message.id)
    )
    llm, _, _ = llm_with(classification())
    await responses.analyze_response(session, llm, r.id)
    return message


async def test_cohorts_are_counted_from_sent_messages_and_replies(
    session: AsyncSession, idea: Idea
) -> None:
    message = await _replied(session, idea)
    row = await experiments.create(
        session,
        idea.id,
        ExperimentCreate(
            hypothesis="Project engineers feel the pain more than directors.",
            cohort_a=Cohort(label="Project engineers", role_contains="project engineer"),
            cohort_b=Cohort(label="Directors", role_contains="Director"),
        ),
    )
    res = await experiments.result(session, row)
    a, b = res["a"], res["b"]
    assert (a["sent"], a["replies"], a["reply_rate"]) == (1, 1, 1.0)
    assert a["positive"] == 1 and a["problem_confirmed"] == 1 and a["interview_recommended"] == 1
    assert (b["sent"], b["replies"], b["reply_rate"]) == (0, 0, None)
    assert a["small_sample"] and b["small_sample"]
    assert "Positive replies: Project engineers 1/1, Directors 0/0." in res["comparison"]
    assert any(line.startswith("Sample too small") for line in res["comparison"])

    # A campaign filter selects by campaign; an unknown campaign is refused.
    by_campaign = await experiments.create(
        session,
        idea.id,
        ExperimentCreate(
            hypothesis="h", cohort_a=Cohort(label="c", campaign_ids=[message.campaign_id])
        ),
    )
    assert (await experiments.result(session, by_campaign))["a"]["sent"] == 1
    try:
        await experiments.create(
            session,
            idea.id,
            ExperimentCreate(
                hypothesis="h", cohort_a=Cohort(label="x", campaign_ids=[uuid.uuid4()])
            ),
        )
        raise AssertionError("expected ExperimentError")
    except experiments.ExperimentError:
        pass


async def test_concluded_results_are_frozen(session: AsyncSession, idea: Idea) -> None:
    await _replied(session, idea)
    row = await experiments.create(
        session, idea.id, ExperimentCreate(hypothesis="h", cohort_a=Cohort(label="All"))
    )
    try:
        await experiments.update(session, row, ExperimentUpdate(status="concluded"))
        raise AssertionError("a conclusion is required")
    except experiments.ExperimentError:
        pass
    row = await experiments.update(
        session, row, ExperimentUpdate(conclusion="Promising.", status="concluded")
    )
    assert row.result["a"]["replies"] == 1 and row.concluded_at

    # The data changes after the experiment ended: the concluded result doesn't.
    [reply] = await responses.list_responses(session, idea.id)
    await responses.delete_response(session, reply)
    assert (await experiments.result(session, row))["a"]["replies"] == 1
    try:
        await experiments.update(session, row, ExperimentUpdate(hypothesis="changed"))
        raise AssertionError("concluded experiments are fixed")
    except experiments.ExperimentError:
        pass

    row = await experiments.update(session, row, ExperimentUpdate(status="running"))
    assert (await experiments.result(session, row))["a"]["replies"] == 0


async def test_experiments_api(
    client: AsyncClient, session_maker: async_sessionmaker[AsyncSession]
) -> None:
    idea = await api_idea(client, session_maker)
    base = f"/ideas/{idea.id}/experiments"
    created = await client.post(
        base, json={"hypothesis": "Ops directors reply more", "cohort_a": {"label": "Everyone"}}
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "running" and body["result"]["a"]["sent"] == 0
    assert body["result"]["b"] is None and body["result"]["comparison"] == []

    eid = body["id"]
    assert [e["id"] for e in (await client.get(base)).json()] == [eid]
    bad = await client.patch(f"{base}/{eid}", json={"status": "concluded"})
    assert bad.status_code == 422
    done = await client.patch(
        f"{base}/{eid}", json={"conclusion": "Not enough data.", "status": "concluded"}
    )
    assert done.status_code == 200 and done.json()["status"] == "concluded"
    bad = await client.post(
        base, json={"hypothesis": "h", "cohort_a": {"label": "x", "icp_id": str(uuid.uuid4())}}
    )
    assert bad.status_code == 422
    assert (await client.delete(f"{base}/{eid}")).status_code == 204
    assert (await client.get(f"{base}/{eid}")).status_code == 404
