"""Research score v2 (Phase 6B): pure rules plus the endpoint and portfolio field."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.research import service as research
from app.modules.validation.research_score import (
    CompetitorEntry,
    QuestionInput,
    ResearchScoreInput,
    ResearchSource,
    research_score,
)
from tests.research_fixtures import evidence_item, pack
from tests.test_research_service import FakeFetcher

_n = 0


def src(
    domain,
    stance="supports",
    source_type="forum",
    cats=(),
    verification="verified",
    relevance="high",
):
    global _n
    _n += 1
    return ResearchSource(
        f"ev-{_n}", domain, stance, relevance, verification, source_type, tuple(cats)
    )


def dims(result):
    return {d.key: d.points for d in result.dimensions}


def score(**kw):
    return dims(research_score(ResearchScoreInput(**kw)))


def test_empty_input_scores_zero_except_open_space() -> None:
    r = research_score(ResearchScoreInput())
    assert sum(d.max for d in r.dimensions) == 100
    assert dims(r) == {
        "problem": 0,
        "pain": 0,
        "balance": 0,
        "questions": 0,
        "open_space": 15,
        "reachability": 0,
    }
    assert r.band == "weak" and r.version == 2


def test_only_verified_medium_high_and_once_per_domain() -> None:
    research = (
        src("a.com"),
        src("a.com"),  # same domain: one source
        src("c.com", relevance="low"),  # not counted
        src("d.com", verification="unverifiable"),  # not counted
    )
    assert score(research=research)["problem"] == score(research=(src("a.com"),))["problem"]


def test_source_type_weighting() -> None:
    forums = tuple(src(f"f{i}.com", source_type="forum") for i in range(4))
    vendors = tuple(src(f"v{i}.com", source_type="company_site") for i in range(4))
    assert score(research=forums)["problem"] > score(research=vendors)["problem"]
    # a domain counts at its best source type
    mixed = (src("x.com", source_type="company_site"), src("x.com", source_type="forum"))
    assert score(research=mixed)["problem"] == score(research=(src("y.com"),))["problem"]


def test_problem_and_pain_never_saturate() -> None:
    def problem_for(n):
        return score(research=tuple(src(f"s{i}.com", cats=("cost",)) for i in range(n)))

    small, big, huge = problem_for(5), problem_for(20), problem_for(200)
    assert small["problem"] < big["problem"] < huge["problem"] <= 25
    assert big["problem"] < 25 and big["pain"] < 15
    assert small["pain"] < big["pain"]


def test_pain_needs_cost_urgency_or_frequency_link() -> None:
    research = (src("a.com", cats=("buyer",)), src("b.com", cats=("other",)))
    assert score(research=research)["pain"] == 0
    assert score(research=(src("a.com", cats=("urgency",)),))["pain"] > 0


def test_balance() -> None:
    eight = tuple(src(f"s{i}.com") for i in range(8))
    assert score(research=eight)["balance"] == 20
    mixed = eight[:4] + tuple(src(f"c{i}.com", stance="contradicts") for i in range(4))
    assert score(research=mixed)["balance"] == 10
    assert score(research=(src("one.com"),))["balance"] == 2  # 20 * 1 * 1/8
    assert score(research=(src("x.com", stance="contradicts"),))["balance"] == 0


def test_open_space_falls_with_evidenced_direct_and_indirect_competitors() -> None:
    e = src("a.com")
    u = src("b.com", verification="unverifiable")

    def open_space(*entries):
        return score(research=(e, u), competitors=entries)["open_space"]

    assert open_space() == 15
    assert open_space(CompetitorEntry("direct", (e.evidence_id,))) == 12
    assert open_space(CompetitorEntry("indirect", (e.evidence_id,))) == 14
    assert open_space(CompetitorEntry("manual", (e.evidence_id,))) == 15  # not crowding
    assert open_space(CompetitorEntry("service", (e.evidence_id,))) == 15
    assert open_space(CompetitorEntry("direct", (u.evidence_id,))) == 15  # unverified: ignored
    assert open_space(*[CompetitorEntry("direct", (e.evidence_id,))] * 6) == 0  # floored


def test_questions_weighted_by_priority() -> None:
    qs = (
        QuestionInput("q1", "high", "answered"),  # 3 of 3
        QuestionInput("q2", "medium", "partially_answered"),  # 1 of 2
        QuestionInput("q3", "low", None),  # 0 of 1
    )
    assert score(questions=qs)["questions"] == 7  # 10*4/6


def test_reachability_caps() -> None:
    assert score(companies=40, contacts=40)["reachability"] == 15
    assert score(companies=3, contacts=1)["reachability"] == 4


def test_deterministic() -> None:
    inp = ResearchScoreInput(
        research=tuple(src(f"s{i}.com", cats=("cost",)) for i in range(10)),
        questions=(QuestionInput("q", "high", "answered"),),
        companies=3,
    )
    assert research_score(inp) == research_score(inp)


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
    assert by_key["problem"]["points"] == 4  # one verified forum domain: round(25*3/18)
    assert by_key["balance"]["points"] == 2
    assert by_key["open_space"]["points"] == 15
    assert data["total"] == sum(d["points"] for d in data["dimensions"]) and data["version"] == 2

    board = (await client.get("/portfolio")).json()
    assert board[0]["research_score"] == {
        "total": data["total"],
        "band": data["band"],
        "version": 2,
    }


async def test_research_score_requires_own_idea(client: AsyncClient) -> None:
    assert (await client.get(f"/ideas/{uuid.uuid4()}/research-score")).status_code == 404


async def test_dropped_questions_do_not_count(client: AsyncClient) -> None:
    body = {"title": "Q", "description": "d", "target_market": "US"}
    idea = (await client.post("/ideas", json=body)).json()["id"]
    await client.post(f"/ideas/{idea}/unknowns", json={"question": "Kept?"})
    dup = (await client.post(f"/ideas/{idea}/unknowns", json={"question": "Kept?"})).json()

    def questions(data):
        return next(d for d in data["dimensions"] if d["key"] == "questions")["reason"]

    before = (await client.get(f"/ideas/{idea}/research-score")).json()
    assert "of 2 questions" in questions(before)
    await client.patch(f"/ideas/{idea}/unknowns/{dup['id']}", json={"status": "dropped"})
    after = (await client.get(f"/ideas/{idea}/research-score")).json()
    assert "of 1 question" in questions(after)
