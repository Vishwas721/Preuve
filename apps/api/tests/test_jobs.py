import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.analysis import service
from app.modules.analysis.models import AnalysisRun, RunKind, RunStatus
from app.modules.ideas.schemas import IdeaCreate
from app.modules.ideas.service import create_idea
from app.modules.users.service import get_or_create_user
from app.workers import jobs


async def test_crashed_job_marks_run_failed(
    session_maker: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    async with session_maker() as s:
        user = await get_or_create_user(s, "j@preuve.local", "J")
        idea = await create_idea(
            s, user.id, IdeaCreate(title="t", description="d", target_market="US")
        )
        run = await service.start_run(s, idea, RunKind.FULL)
        run_id = run.id

    async def boom(*args, **kwargs):
        raise RuntimeError("mapper exploded")

    monkeypatch.setattr(jobs, "SessionLocal", session_maker)
    monkeypatch.setattr(jobs.analysis, "execute_run", boom)
    monkeypatch.setattr(jobs, "get_llm_router", lambda: None)

    with pytest.raises(RuntimeError):
        await jobs.run_analysis({}, str(run_id))

    async with session_maker() as s:
        run = await s.get(AnalysisRun, run_id)
        assert run.status == RunStatus.FAILED
        assert "mapper exploded" in run.error


async def test_crashed_research_job_marks_import_failed(
    session_maker: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.research import service as research
    from app.modules.research.models import ImportStatus, ResearchImport
    from app.modules.research.pack import ResearchPack
    from tests.research_fixtures import pack

    async with session_maker() as s:
        user = await get_or_create_user(s, "k@preuve.local", "K")
        idea = await create_idea(
            s, user.id, IdeaCreate(title="t", description="d", target_market="US")
        )
        imp = await research.create_import(s, idea, ResearchPack.model_validate(pack(idea.id)))
        import_id = imp.id

    async def boom(*args, **kwargs):
        raise RuntimeError("fetcher exploded")

    monkeypatch.setattr(jobs, "SessionLocal", session_maker)
    monkeypatch.setattr(jobs.research, "verify_import", boom)

    with pytest.raises(RuntimeError):
        await jobs.verify_research_import({}, str(import_id))

    async with session_maker() as s:
        imp = await s.get(ResearchImport, import_id)
        assert imp.status == ImportStatus.FAILED and "fetcher exploded" in imp.error
