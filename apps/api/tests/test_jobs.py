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
