from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import LLMUnavailableError
from app.modules.analysis import service
from app.modules.analysis.models import (
    AnalysisRun,
    ICPStatus,
    RunKind,
    RunStatus,
    Source,
    UnknownStatus,
)
from app.modules.analysis.prompts import NO_FACTS_RULES, ICPRatings
from app.modules.analysis.schemas import (
    HypothesisEdit,
    ICPCreate,
    ICPUpdate,
    UnknownCreate,
    UnknownUpdate,
)
from app.modules.ideas.models import Idea
from app.modules.ideas.schemas import IdeaCreate
from app.modules.ideas.service import create_idea
from app.modules.users.service import get_or_create_user
from app.modules.workspaces.service import personal_workspace_id
from tests.analysis_fixtures import analysis_output, icp, icps_output, make_router, ratings


@pytest.fixture
async def idea(session: AsyncSession) -> Idea:
    user = await get_or_create_user(session, "t@preuve.local", "T")
    return await create_idea(
        session,
        await personal_workspace_id(session, user),
        IdeaCreate(
            title="Construction AI",
            description="AI tool that automates construction progress reports.",
            target_market="United States",
        ),
    )


async def run_full(session: AsyncSession, idea: Idea, gemini_outputs: list) -> AnalysisRun:
    router, _, gemini = make_router()
    gemini.queue(*gemini_outputs)
    run = await service.start_run(session, idea, RunKind.FULL)
    await service.execute_run(session, router, run.id)
    await session.refresh(run)
    return run


async def test_full_run_creates_hypothesis_unknowns_and_scored_icps(
    session: AsyncSession, idea: Idea
) -> None:
    run = await run_full(
        session,
        idea,
        [analysis_output(), icps_output(icp("Low", pain=2), icp("High", pain=5, pay=5))],
    )
    assert run.status == RunStatus.SUCCEEDED
    assert run.step == "icps" and run.started_at and run.finished_at

    hyp = await service.get_current_hypothesis(session, idea.id)
    assert hyp.version == 1 and hyp.source == Source.AI

    unknowns = await service.list_unknowns(session, idea.id)
    assert len(unknowns) == 3
    assert all(u.source == Source.AI and u.status == UnknownStatus.OPEN for u in unknowns)

    icps = await service.list_icps(session, idea.id)
    assert [i.name for i in icps] == ["High", "Low"]
    assert icps[0].is_primary and not icps[1].is_primary
    # pain 5, pay 5, rest 3: 30 + 25 + 10 + 7.5 + 5 = 77.5 -> 78
    assert icps[0].hypothesis_score == 78


async def test_prompts_carry_no_facts_rules_and_wrap_founder_input(
    session: AsyncSession, idea: Idea
) -> None:
    router, _, gemini = make_router()
    gemini.queue(analysis_output(), icps_output())
    run = await service.start_run(session, idea, RunKind.FULL)
    await service.execute_run(session, router, run.id)
    analyze_call, icps_call = gemini.calls
    for call in (analyze_call, icps_call):
        assert NO_FACTS_RULES in call.system
        assert "<founder_input>" in call.prompt
    assert "automates construction progress reports" in analyze_call.prompt


async def test_rerun_keeps_user_work(session: AsyncSession, idea: Idea) -> None:
    await run_full(session, idea, [analysis_output(), icps_output(icp("AI one"))])
    first_ai_unknown = (await service.list_unknowns(session, idea.id))[0]
    await service.update_unknown(session, first_ai_unknown, UnknownUpdate(question="Edited?"))
    mine = await service.create_icp(
        session,
        idea.id,
        ICPCreate(
            name="Mine",
            company_type="Specialty contractors",
            geography="US",
            ratings=ICPRatings.model_validate(ratings()),
            is_primary=True,
        ),
    )

    run = await run_full(
        session, idea, [analysis_output("v2 problem", n_unknowns=4), icps_output(icp("AI two"))]
    )
    assert run.status == RunStatus.SUCCEEDED

    hyp = await service.get_current_hypothesis(session, idea.id)
    assert (hyp.version, hyp.problem) == (2, "v2 problem")

    unknowns = await service.list_unknowns(session, idea.id)
    assert sum(u.source == Source.USER for u in unknowns) == 1  # the edited one survived
    assert sum(u.source == Source.AI for u in unknowns) == 4  # old AI ones dropped
    dropped = await service.list_unknowns(session, idea.id, include_dropped=True)
    assert len(dropped) == 1 + 4 + 2

    icps = {i.name: i for i in await service.list_icps(session, idea.id)}
    assert set(icps) == {"Mine", "AI two"}
    assert icps["Mine"].is_primary and not icps["AI two"].is_primary
    assert mine.id == icps["Mine"].id


async def test_icp_step_failure_keeps_hypothesis(session: AsyncSession, idea: Idea) -> None:
    router, local, gemini = make_router()
    gemini.queue(analysis_output(), LLMUnavailableError("gemini down"))
    local.queue(LLMUnavailableError("ollama down"))
    idea_id = idea.id  # the failed run rolls back the shared session, expiring `idea`
    run = await service.start_run(session, idea, RunKind.FULL)
    assert await service.execute_run(session, router, run.id) == RunStatus.FAILED
    await session.refresh(run)
    assert "icps" in run.error
    assert await service.get_current_hypothesis(session, idea_id) is not None
    assert await service.list_icps(session, idea_id) == []


async def test_invalid_output_fails_run(session: AsyncSession, idea: Idea) -> None:
    idea_id = idea.id
    too_few = analysis_output(n_unknowns=2)  # schema requires at least 3
    run = await run_full(session, idea, [too_few, too_few])
    assert run.status == RunStatus.FAILED
    assert await service.get_current_hypothesis(session, idea_id) is None


async def test_icps_only_run(session: AsyncSession, idea: Idea) -> None:
    await run_full(session, idea, [analysis_output(), icps_output(icp("First"))])
    router, _, gemini = make_router()
    gemini.queue(icps_output(icp("Second")))
    run = await service.start_run(session, idea, RunKind.ICPS)
    assert await service.execute_run(session, router, run.id) == RunStatus.SUCCEEDED
    assert [i.name for i in await service.list_icps(session, idea.id)] == ["Second"]
    assert (await service.get_current_hypothesis(session, idea.id)).version == 1


async def test_start_run_guards(session: AsyncSession, idea: Idea) -> None:
    with pytest.raises(service.NoHypothesisError):
        await service.start_run(session, idea, RunKind.ICPS)

    run = await service.start_run(session, idea, RunKind.FULL)
    with pytest.raises(service.ActiveRunError):
        await service.start_run(session, idea, RunKind.FULL)

    run.created_at = run.created_at - service.STALE_RUN_AFTER - timedelta(minutes=1)
    await session.commit()
    fresh = await service.start_run(session, idea, RunKind.FULL)
    await session.refresh(run)
    assert run.status == RunStatus.FAILED and "Timed out" in run.error
    assert fresh.status == RunStatus.QUEUED


async def test_hypothesis_edit_appends_version(session: AsyncSession, idea: Idea) -> None:
    await run_full(session, idea, [analysis_output(), icps_output()])
    edit = HypothesisEdit(**analysis_output("Edited problem")["hypothesis"], change_note="tighter")
    hyp = await service.save_hypothesis_edit(session, idea.id, edit)
    assert (hyp.version, hyp.source, hyp.change_note) == (2, Source.USER, "tighter")
    versions = await service.list_hypothesis_versions(session, idea.id)
    assert [v.version for v in versions] == [2, 1]


async def test_unknown_source_flips_only_on_content_edit(session: AsyncSession, idea: Idea) -> None:
    await run_full(session, idea, [analysis_output(), icps_output()])
    u = (await service.list_unknowns(session, idea.id))[0]
    u = await service.update_unknown(session, u, UnknownUpdate(status=UnknownStatus.ANSWERED))
    assert u.source == Source.AI
    u = await service.update_unknown(session, u, UnknownUpdate(priority="low"))
    assert u.source == Source.USER
    created = await service.create_unknown(session, idea.id, UnknownCreate(question="Mine?"))
    assert created.source == Source.USER and created.status == UnknownStatus.OPEN


async def test_icp_update_rescores_and_manages_primary(session: AsyncSession, idea: Idea) -> None:
    await run_full(session, idea, [analysis_output(), icps_output(icp("A", pain=5), icp("B"))])
    a, b = await service.list_icps(session, idea.id)
    assert a.is_primary

    b = await service.update_icp(
        session, b, ICPUpdate(ratings=ICPRatings.model_validate(ratings(5, 5, 5, 5, 5)))
    )
    assert b.hypothesis_score == 100 and b.source == Source.USER

    b = await service.update_icp(session, b, ICPUpdate(is_primary=True))
    await session.refresh(a)
    assert b.is_primary and not a.is_primary

    b = await service.update_icp(session, b, ICPUpdate(status=ICPStatus.DISMISSED))
    assert not b.is_primary
    assert [i.name for i in await service.list_icps(session, idea.id)] == ["A"]
