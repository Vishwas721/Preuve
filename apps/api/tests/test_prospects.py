import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.analysis import service as analysis
from app.modules.analysis.schemas import ICPCreate
from app.modules.ideas.models import Idea
from app.modules.ideas.schemas import IdeaCreate
from app.modules.ideas.service import create_idea
from app.modules.prospects import service as prospects
from app.modules.prospects.models import Contact, LeadScore
from app.modules.research import service as research
from app.modules.users.service import get_or_create_user
from app.modules.workspaces.service import personal_workspace_id
from app.search.fetch import FetchError
from tests.research_fixtures import evidence_item, pack
from tests.test_research_service import FakeFetcher, run_import

ABOUT = (
    "ABC Builders is a commercial general contractor headquartered in Dallas, Texas. "
    "Our team of over 200 employees delivers healthcare projects. "
    "Leadership: Jane Roe, Project Engineer. Sam Poe, Chief Financial Officer. "
    "Contact us at info@abcbuilders.com."
)
JOBS = "Project Coordinator at ABC Builders: prepare weekly progress reports for owners."
ROBOT_BLOCKED = "https://blocked.example/team"


def assessment(rating: int, refs: list[str]) -> dict:
    return {"rating": rating, "rationale": f"rated {rating}", "evidence_refs": refs}


def company(**overrides) -> dict:
    item = {
        "ref": "co-01",
        "name": "ABC Builders",
        "website": "https://www.abcbuilders.com",
        "location": "Dallas, TX",
        "industry": "Commercial construction",
        "description": "Commercial GC",
        "size_estimate": {
            "min": 200,
            "signal": "About page: over 200 employees",
            "evidence_ref": "ev-02",
        },
        "in_target_geography": {"value": True, "evidence_ref": "ev-01"},
        "evidence_refs": ["ev-01", "ev-03"],
        "assessments": {
            "company_fit": assessment(4, ["ev-01"]),
            "technology_fit": assessment(3, []),  # no evidence -> 0 points
            "other_signals": assessment(0, []),
        },
        "contacts": [
            {"name": "Jane Roe", "role": "Project Engineer", "evidence_ref": "ev-04"},
        ],
    }
    return item | overrides


def evidence() -> list[dict]:
    about = "https://abcbuilders.com/about"
    return [
        evidence_item(
            "ev-01",
            url=about,
            quote="commercial general contractor headquartered in Dallas, Texas",
            stance="neutral",
        ),
        evidence_item("ev-02", url=about, quote="Our team of over 200 employees", stance="neutral"),
        evidence_item(
            "ev-03",
            url="https://jobs.example/abc",
            quote="prepare weekly progress reports for owners",
            stance="supports",
        ),
        evidence_item("ev-04", url=about, quote="Jane Roe, Project Engineer", stance="neutral"),
        evidence_item(
            "ev-05", url=about, quote="Sam Poe, Chief Financial Officer", stance="neutral"
        ),
        evidence_item(
            "ev-06", url=ROBOT_BLOCKED, quote="Pat Doe, Director of Operations", stance="neutral"
        ),
    ]


PAGES = {
    "https://abcbuilders.com/about": ABOUT,
    "https://jobs.example/abc": JOBS,
    ROBOT_BLOCKED: FetchError("Disallowed by robots.txt"),
}


@pytest.fixture
async def idea(session: AsyncSession) -> Idea:
    user = await get_or_create_user(session, "p@preuve.local", "P")
    idea = await create_idea(
        session,
        await personal_workspace_id(session, user),
        IdeaCreate(title="t", description="d", target_market="US"),
    )
    ratings = {
        k: {"rating": 3, "rationale": "r"}
        for k in (
            "pain_likelihood",
            "ability_to_pay",
            "reachability",
            "frequency_urgency",
            "segment_size",
        )
    }
    await analysis.create_icp(
        session,
        idea.id,
        ICPCreate(
            name="Mid-size GCs",
            company_type="General contractors",
            geography="US",
            size_min=50,
            size_max=500,
            user_roles=["Project Engineers"],
            buyer_roles=["CFO"],
            ratings=ratings,
            is_primary=True,
        ),
    )
    return idea


async def import_company(session, idea, comp=None, pages=PAGES):
    body = pack(idea.id, evidence(), companies=[comp or company()])
    return await run_import(session, idea, body, FakeFetcher(pages))


def components(detail: dict) -> dict:
    return {c["key"]: c for c in detail["components"]}


async def test_company_import_scores_with_reasons(session: AsyncSession, idea: Idea) -> None:
    imp = await import_company(session, idea)
    assert imp.report["companies"]["created"] == ["ABC Builders"]

    [row] = await prospects.list_prospects(session, idea.id)
    company_obj = await prospects.get_company(session, idea.id, row["id"])
    detail = await prospects.prospect_detail(session, company_obj)
    c = components(detail)
    assert c["company_fit"]["points"] == 16 and c["company_fit"]["evidence_ids"]
    assert c["problem_evidence"]["points"] == 15  # one verified supporting item
    assert c["role_relevance"]["points"] == 12  # Project Engineer = ICP user role
    assert c["company_size"]["points"] == 5  # 200+ overlaps 50–500
    assert c["geography"]["points"] == 5
    assert (
        c["technology_fit"]["points"] == 0 and "no stored evidence" in c["technology_fit"]["reason"]
    )
    assert detail["score"] == 53 == sum(round(x["points"]) for x in detail["components"])
    assert all(x["reason"] for x in detail["components"])


async def test_contact_privacy_rules(session: AsyncSession, idea: Idea) -> None:
    comp = company(
        contacts=[
            {
                "name": "Jane Roe",
                "role": "Project Engineer",
                "evidence_ref": "ev-04",
                "email": "jane.roe@abcbuilders.com",
            },  # not printed on the page
            {
                "name": "Sam Poe",
                "role": "Chief Financial Officer",
                "evidence_ref": "ev-05",
                "email": "info@abcbuilders.com",
            },  # printed on the page
            {"name": "Bob Fake", "role": "CEO", "evidence_ref": "ev-05"},  # not in the quote
            {
                "name": "Pat Doe",
                "role": "Director of Operations",
                "evidence_ref": "ev-06",
            },  # unverifiable
        ]
    )
    imp = await import_company(session, idea, comp)
    reasons = {r["name"]: r["reason"] for r in imp.report["companies"]["contacts_rejected"]}
    assert "email not found" in reasons["Jane Roe"]
    assert "does not appear" in reasons["Bob Fake"]
    assert "not verified" in reasons["Pat Doe"]

    contacts = {c.name: c for c in await session.scalars(select(Contact))}
    assert set(contacts) == {"Jane Roe", "Sam Poe"}
    assert contacts["Jane Roe"].email is None  # never guessed
    assert contacts["Sam Poe"].email == "info@abcbuilders.com"
    assert contacts["Sam Poe"].source_url == "https://abcbuilders.com/about"

    [row] = await prospects.list_prospects(session, idea.id)
    detail = await prospects.prospect_detail(
        session, await prospects.get_company(session, idea.id, row["id"])
    )
    assert components(detail)["role_relevance"]["points"] == 20  # CFO = buyer role


async def test_company_without_stored_evidence_rejected(session: AsyncSession, idea: Idea) -> None:
    comp = company(evidence_refs=["ev-03"], contacts=[])
    pages = PAGES | {"https://jobs.example/abc": "a page that no longer mentions reports"}
    imp = await import_company(session, idea, comp, pages)
    assert imp.report["companies"]["rejected"][0]["name"] == "ABC Builders"
    assert await prospects.list_prospects(session, idea.id) == []


async def test_reimport_merges_by_domain_and_keeps_status(
    session: AsyncSession, idea: Idea
) -> None:
    await import_company(session, idea)
    [row] = await prospects.list_prospects(session, idea.id)
    company_obj = await prospects.get_company(session, idea.id, row["id"])
    company_obj.status = "shortlisted"
    await session.commit()

    imp = await import_company(session, idea, company(website="https://abcbuilders.com/"))
    assert imp.report["companies"]["updated"] == ["ABC Builders"]
    [row] = await prospects.list_prospects(session, idea.id)
    assert row["status"] == "shortlisted" and row["contacts"] == 1
    # same inputs -> no extra score row
    count = await session.scalar(select(func.count()).select_from(LeadScore))
    assert count == 1


async def test_rescore_is_deterministic_and_follows_icp(session: AsyncSession, idea: Idea) -> None:
    await import_company(session, idea)
    [row] = await prospects.list_prospects(session, idea.id)
    company_obj = await prospects.get_company(session, idea.id, row["id"])
    before = await prospects.prospect_detail(session, company_obj)

    await prospects.rescore_idea(session, idea.id)
    after = await prospects.prospect_detail(session, company_obj)
    assert (before["score"], before["inputs_hash"]) == (after["score"], after["inputs_hash"])

    ratings = {
        k: {"rating": 3, "rationale": "r"}
        for k in (
            "pain_likelihood",
            "ability_to_pay",
            "reachability",
            "frequency_urgency",
            "segment_size",
        )
    }
    icp2 = await analysis.create_icp(
        session,
        idea.id,
        ICPCreate(
            name="Engineers buy",
            company_type="GC",
            geography="US",
            buyer_roles=["Project Engineer"],
            ratings=ratings,
        ),
    )
    from app.modules.prospects.schemas import ProspectUpdate

    await prospects.update_prospect(session, company_obj, ProspectUpdate(icp_id=icp2.id))
    detail = await prospects.prospect_detail(session, company_obj)
    assert components(detail)["role_relevance"]["points"] == 20
    assert components(detail)["company_size"]["points"] == 5  # new ICP has no size band


async def test_delete_contact_removes_person_and_rescores(
    session: AsyncSession, idea: Idea
) -> None:
    await import_company(session, idea)
    contact = await session.scalar(select(Contact))
    assert await prospects.delete_contact(session, idea.id, contact.id)
    assert await session.scalar(select(func.count()).select_from(Contact)) == 0
    [row] = await prospects.list_prospects(session, idea.id)
    detail = await prospects.prospect_detail(
        session, await prospects.get_company(session, idea.id, row["id"])
    )
    assert components(detail)["role_relevance"]["points"] == 0
    assert not await prospects.delete_contact(session, idea.id, contact.id)


async def test_evidence_labels(session: AsyncSession, idea: Idea) -> None:
    await import_company(session, idea)
    rows = await research.list_evidence(session, idea.id)
    labels = await research.evidence_labels(session, [r["id"] for r in rows])
    assert {v for v, _ in labels.values()} == {"verified", "unverifiable"}


# ---------- API ----------


async def test_prospect_api(
    client: AsyncClient, session_maker: async_sessionmaker[AsyncSession]
) -> None:
    async with session_maker() as s:
        user = await get_or_create_user(s, "founder@preuve.local", "Founder")
        idea = await create_idea(
            s,
            await personal_workspace_id(s, user),
            IdeaCreate(title="t", description="d", target_market="US"),
        )
        await import_company(s, idea)
        idea_id = idea.id
    base = f"/ideas/{idea_id}"

    rows = (await client.get(f"{base}/prospects")).json()
    assert len(rows) == 1 and rows[0]["score"] is not None
    pid = rows[0]["id"]
    assert (await client.get(f"{base}/prospects", params={"min_score": 99})).json() == []
    assert (await client.get(f"{base}/prospects", params={"status": "excluded"})).json() == []

    detail = (await client.get(f"{base}/prospects/{pid}")).json()
    assert len(detail["components"]) == 7 and detail["contacts_list"][0]["source_url"]

    patched = await client.patch(f"{base}/prospects/{pid}", json={"status": "shortlisted"})
    assert patched.json()["status"] == "shortlisted"
    bad_icp = await client.patch(f"{base}/prospects/{pid}", json={"icp_id": str(uuid.uuid4())})
    assert bad_icp.status_code == 422

    assert (await client.post(f"{base}/prospects/rescore")).json() == {"rescored": 1}
    contact_id = detail["contacts_list"][0]["id"]
    assert (await client.delete(f"{base}/contacts/{contact_id}")).status_code == 204
    assert (await client.delete(f"{base}/contacts/{contact_id}")).status_code == 404
    assert (await client.get(f"{base}/prospects/{uuid.uuid4()}")).status_code == 404
