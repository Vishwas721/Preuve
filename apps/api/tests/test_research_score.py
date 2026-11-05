"""Phase 6 research score: pure rules plus the endpoint and portfolio field."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.research import service as research
from app.modules.validation.research_score import (
    QuestionInput,
    ResearchScoreInput,
    research_score,
)
from app.modules.validation.scoring import ResearchItem
from tests.research_fixtures import evidence_item, pack
from tests.test_research_service import FakeFetcher

_n = 0


def item(domain, stance="supports", cats=(), verification="verified", relevance="high"):
    global _n
    _n += 1
    return ResearchItem(f"ev-{_n}", domain, stance, relevance, verification, tuple(cats))


def dims(result):
    return {d.key: d.points for d in result.dimensions}


def test_empty_input_scores_zero() -> None:
    r = research_score(ResearchScoreInput())
    assert r.total == 0 and r.band == "weak"
    assert all(d.points == 0 for d in r.dimensions)
    assert sum(d.max for d in r.dimensions) == 100


def test_domains_count_once_and_only_verified_medium_high() -> None:
    research = (
        item("a.com"),
        item("a.com"),  # same domain: one source
        item("b.com", relevance="medium"),
        item("c.com", relevance="low"),  # low relevance: not counted
        item("d.com", verification="unverifiable"),  # not counted
    )
    r = research_score(ResearchScoreInput(research=research))
    assert dims(r)["problem"] == 6  # a.com + b.com


def test_pain_needs_cost_urgency_or_frequency_link() -> None:
    research = (
        item("a.com", cats=("cost",)),
        item("b.com", cats=("buyer",)),
        item("c.com", cats=("urgency", "other")),
    )
    assert dims(research_score(ResearchScoreInput(research=research)))["pain"] == 6


def test_caps_hold() -> None:
    research = tuple(item(f"s{i}.com", cats=("frequency",)) for i in range(20))
    r = research_score(
        ResearchScoreInput(
            research=research,
            competitor_evidence=tuple((x.evidence_id,) for x in research),
            companies=40,
            contacts=40,
        )
    )
    d = dims(r)
    assert (d["problem"], d["pain"], d["balance"], d["alternatives"], d["reachability"]) == (
        30,
        15,
        20,
        5,
        15,
    )
    assert all(x.points <= x.max for x in r.dimensions)


def test_contradictions_lower_balance_and_thin_evidence_is_damped() -> None:
    six = tuple(item(f"s{i}.com") for i in range(6))
    assert dims(research_score(ResearchScoreInput(research=six)))["balance"] == 20
    mixed = six[:3] + tuple(item(f"c{i}.com", stance="contradicts") for i in range(3))
    assert dims(research_score(ResearchScoreInput(research=mixed)))["balance"] == 10
    thin = (item("one.com"),)  # 1 of 5 sources needed for full balance
    assert dims(research_score(ResearchScoreInput(research=thin)))["balance"] == 4
    only_contra = (item("x.com", stance="contradicts"),)
    assert dims(research_score(ResearchScoreInput(research=only_contra)))["balance"] == 0


def test_questions_weighted_by_priority() -> None:
    qs = (
        QuestionInput("q1", "high", "answered"),  # 3 of 3
        QuestionInput("q2", "medium", "partially_answered"),  # 1 of 2
        QuestionInput("q3", "low", None),  # 0 of 1
    )
    assert dims(research_score(ResearchScoreInput(questions=qs)))["questions"] == 10  # 15*4/6


def test_alternatives_need_verified_evidence() -> None:
    v, u = item("a.com"), item("b.com", verification="unverifiable")
    r = research_score(
        ResearchScoreInput(
            research=(v, u), competitor_evidence=((v.evidence_id,), (u.evidence_id,), ())
        )
    )
    assert dims(r)["alternatives"] == 1


def test_deterministic_and_bands() -> None:
    inp = ResearchScoreInput(
        research=tuple(item(f"s{i}.com", cats=("cost",)) for i in range(10)),
        questions=(QuestionInput("q", "high", "answered"),),
        companies=3,
        contacts=1,
    )
    a, b = research_score(inp), research_score(inp)
    assert a == b
    assert a.total == 30 + 15 + 20 + 15 + 0 + 4 and a.band == "strong"


PAGE = "Our project coordinators spend most of Friday compiling weekly progress reports."


async def test_endpoint_and_portfolio(
    client: AsyncClient, session_maker: async_sessionmaker[AsyncSession]
) -> None:
    body = {"title": "Reports", "description": "d", "target_market": "US"}
    idea = (await client.post("/ideas", json=body)).json()["id"]
    items = [
        evidence_item(
            "ev-01", url="https://a.com/1", quote="spend most of Friday compiling weekly"
        ),
        evidence_item("ev-02", url="https://b.com/2", quote="a quote from a blocked page here"),
    ]
    imp = (await client.post(f"/ideas/{idea}/research-imports", json=pack(idea, items))).json()
    async with session_maker() as s:
        from app.search.fetch import FetchError

        fetcher = FakeFetcher({"https://a.com/1": PAGE, "https://b.com/2": FetchError("403")})
        await research.verify_import(s, fetcher, uuid.UUID(imp["id"]), delay=0)

    r = await client.get(f"/ideas/{idea}/research-score")
    assert r.status_code == 200
    data = r.json()
    by_key = {d["key"]: d for d in data["dimensions"]}
    assert by_key["problem"]["points"] == 3  # only the verified a.com counts
    assert by_key["balance"]["points"] == 4
    assert data["total"] == sum(d["points"] for d in data["dimensions"]) and data["version"] == 1

    board = (await client.get("/portfolio")).json()
    assert board[0]["research_score"] == {
        "total": data["total"],
        "band": data["band"],
        "version": 1,
    }


async def test_research_score_requires_own_idea(client: AsyncClient) -> None:
    assert (await client.get(f"/ideas/{uuid.uuid4()}/research-score")).status_code == 404
