import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.router import LLMRouter
from app.llm.tasks import TaskType
from app.modules.analysis import prompts
from app.modules.analysis.models import (
    ICP,
    AnalysisRun,
    Hypothesis,
    ICPStatus,
    RunKind,
    RunStatus,
    Source,
    Unknown,
    UnknownStatus,
)
from app.modules.analysis.rubric import Criterion, Rating, compute_score
from app.modules.analysis.schemas import (
    HypothesisEdit,
    ICPCreate,
    ICPUpdate,
    UnknownCreate,
    UnknownUpdate,
)
from app.modules.ideas.models import Idea

logger = logging.getLogger(__name__)

# A run still "active" after this long is assumed dead (worker crash) and no longer blocks.
STALE_RUN_AFTER = timedelta(minutes=15)


class AnalysisError(Exception):
    """Base class for analysis errors surfaced to the API."""


class ActiveRunError(AnalysisError):
    pass


class NoHypothesisError(AnalysisError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def idea_fields(idea: Idea) -> dict[str, str | None]:
    return {
        "title": idea.title,
        "idea": idea.description,
        "target_market": idea.target_market,
        "why_it_matters": idea.why_it_matters,
        "industry": idea.industry,
        "customer_type": idea.customer_type,
        "business_model": idea.business_model,
        "known_competitors": idea.known_competitors,
        "assumptions": idea.assumptions,
    }


# ---------- runs ----------


async def get_run(
    session: AsyncSession, idea_id: uuid.UUID, run_id: uuid.UUID
) -> AnalysisRun | None:
    return await session.scalar(
        select(AnalysisRun).where(AnalysisRun.id == run_id, AnalysisRun.idea_id == idea_id)
    )


async def latest_run(session: AsyncSession, idea_id: uuid.UUID) -> AnalysisRun | None:
    return await session.scalar(
        select(AnalysisRun)
        .where(AnalysisRun.idea_id == idea_id)
        .order_by(AnalysisRun.created_at.desc())
        .limit(1)
    )


async def start_run(session: AsyncSession, idea: Idea, kind: RunKind) -> AnalysisRun:
    """Create a queued run. Enqueueing the job is the caller's job."""
    active = await session.scalar(
        select(AnalysisRun).where(
            AnalysisRun.idea_id == idea.id,
            AnalysisRun.status.in_([RunStatus.QUEUED, RunStatus.RUNNING]),
        )
    )
    if active is not None:
        if active.created_at > _now() - STALE_RUN_AFTER:
            raise ActiveRunError("An analysis is already running for this idea")
        active.status = RunStatus.FAILED
        active.error = "Timed out (worker stopped?)"
        active.finished_at = _now()

    if kind == RunKind.ICPS and await get_current_hypothesis(session, idea.id) is None:
        raise NoHypothesisError("Analyze the idea before generating ICPs")

    run = AnalysisRun(idea_id=idea.id, kind=kind, status=RunStatus.QUEUED)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def fail_run(session: AsyncSession, run: AnalysisRun, error: str) -> None:
    run.status = RunStatus.FAILED
    run.error = error[:2000]
    run.finished_at = _now()
    await session.commit()


async def fail_if_active(session: AsyncSession, run_id: uuid.UUID, error: str) -> None:
    """Safety net for crashes outside `execute_run`'s own error handling."""
    run = await session.get(AnalysisRun, run_id)
    if run is not None and run.status in (RunStatus.QUEUED, RunStatus.RUNNING):
        await fail_run(session, run, error)


async def execute_run(session: AsyncSession, llm: LLMRouter, run_id: uuid.UUID) -> RunStatus:
    """Run the analysis steps for `run_id`. Each finished step is committed, so a later
    failure (e.g. ICPs) keeps earlier work (the hypothesis) and can be retried on its own."""
    run = await session.get(AnalysisRun, run_id)
    if run is None:
        raise ValueError(f"Analysis run {run_id} not found")
    idea = await session.get(Idea, run.idea_id)
    if idea is None:
        await fail_run(session, run, "Idea was deleted")
        return run.status

    run.status = RunStatus.RUNNING
    run.started_at = _now()
    await session.commit()

    try:
        if run.kind == RunKind.FULL:
            run.step = "hypothesis"
            await session.commit()
            await _generate_hypothesis(session, llm, idea)

        run.step = "icps"
        await session.commit()
        await _generate_icps(session, llm, idea)
    except Exception as exc:
        step = run.step  # read before rollback expires the instance
        logger.exception("analysis run %s failed at step %s", run_id, step)
        await session.rollback()
        await session.refresh(run)
        await fail_run(session, run, f"Failed at step '{step}': {exc}")
        return run.status

    run.status = RunStatus.SUCCEEDED
    run.finished_at = _now()
    await session.commit()
    return run.status


async def _generate_hypothesis(session: AsyncSession, llm: LLMRouter, idea: Idea) -> None:
    result = await llm.structured(
        TaskType.ANALYZE_IDEA,
        prompts.analyze_prompt(idea_fields(idea)),
        prompts.IdeaAnalysis,
        system=prompts.ANALYZE_SYSTEM,
    )
    await add_hypothesis_version(
        session, idea.id, result.hypothesis.model_dump(), Source.AI, "Generated by AI"
    )
    # Replace only untouched AI unknowns; anything the user created or edited stays.
    await session.execute(
        update(Unknown)
        .where(
            Unknown.idea_id == idea.id,
            Unknown.source == Source.AI,
            Unknown.status == UnknownStatus.OPEN,
        )
        .values(status=UnknownStatus.DROPPED)
    )
    for u in result.unknowns:
        session.add(
            Unknown(
                idea_id=idea.id,
                question=u.question,
                category=u.category,
                priority=u.priority,
                status=UnknownStatus.OPEN,
                source=Source.AI,
            )
        )
    await session.commit()


async def _generate_icps(session: AsyncSession, llm: LLMRouter, idea: Idea) -> None:
    hypothesis = await get_current_hypothesis(session, idea.id)
    if hypothesis is None:
        raise NoHypothesisError("No hypothesis to base ICPs on")
    draft = prompts.HypothesisDraft.model_validate(hypothesis, from_attributes=True)
    result = await llm.structured(
        TaskType.GENERATE_ICPS,
        prompts.icps_prompt(idea_fields(idea), draft),
        prompts.ICPSet,
        system=prompts.ICPS_SYSTEM,
    )
    await session.execute(
        update(ICP)
        .where(ICP.idea_id == idea.id, ICP.source == Source.AI, ICP.status == ICPStatus.ACTIVE)
        .values(status=ICPStatus.DISMISSED, is_primary=False)
    )
    has_primary = await session.scalar(
        select(func.count())
        .select_from(ICP)
        .where(ICP.idea_id == idea.id, ICP.status == ICPStatus.ACTIVE, ICP.is_primary)
    )
    # Highest-scoring new ICP becomes primary unless the user already chose one.
    drafts = sorted(result.icps, key=lambda d: compute_score(d.ratings.as_dict()), reverse=True)
    for i, d in enumerate(drafts):
        session.add(
            _icp_from_fields(
                idea.id,
                name=d.name,
                company_type=d.company_type,
                size_min=d.size_min,
                size_max=d.size_max,
                geography=d.geography,
                signals=d.signals,
                user_roles=d.user_roles,
                buyer_roles=d.buyer_roles,
                ratings=d.ratings.as_dict(),
                source=Source.AI,
                is_primary=(i == 0 and not has_primary),
            )
        )
    await session.commit()


# ---------- hypothesis ----------


async def get_current_hypothesis(session: AsyncSession, idea_id: uuid.UUID) -> Hypothesis | None:
    return await session.scalar(
        select(Hypothesis)
        .where(Hypothesis.idea_id == idea_id)
        .order_by(Hypothesis.version.desc())
        .limit(1)
    )


async def list_hypothesis_versions(session: AsyncSession, idea_id: uuid.UUID) -> list[Hypothesis]:
    result = await session.scalars(
        select(Hypothesis).where(Hypothesis.idea_id == idea_id).order_by(Hypothesis.version.desc())
    )
    return list(result)


async def add_hypothesis_version(
    session: AsyncSession,
    idea_id: uuid.UUID,
    fields: dict,
    source: Source,
    change_note: str | None,
) -> Hypothesis:
    current = await session.scalar(
        select(func.max(Hypothesis.version)).where(Hypothesis.idea_id == idea_id)
    )
    """Append a new version (does not commit). Used by analysis, user edits and research."""
    hypothesis = Hypothesis(
        idea_id=idea_id,
        version=(current or 0) + 1,
        source=source,
        change_note=change_note,
        **fields,
    )
    session.add(hypothesis)
    await session.flush()
    return hypothesis


async def save_hypothesis_edit(
    session: AsyncSession, idea_id: uuid.UUID, data: HypothesisEdit
) -> Hypothesis:
    fields = data.model_dump(exclude={"change_note"})
    hypothesis = await add_hypothesis_version(
        session, idea_id, fields, Source.USER, data.change_note or "Edited by you"
    )
    await session.commit()
    await session.refresh(hypothesis)
    return hypothesis


# ---------- unknowns ----------


async def list_unknowns(
    session: AsyncSession, idea_id: uuid.UUID, include_dropped: bool = False
) -> list[Unknown]:
    query = select(Unknown).where(Unknown.idea_id == idea_id)
    if not include_dropped:
        query = query.where(Unknown.status != UnknownStatus.DROPPED)
    result = await session.scalars(query.order_by(Unknown.created_at))
    return list(result)


async def get_unknown(
    session: AsyncSession, idea_id: uuid.UUID, unknown_id: uuid.UUID
) -> Unknown | None:
    return await session.scalar(
        select(Unknown).where(Unknown.id == unknown_id, Unknown.idea_id == idea_id)
    )


def add_unknown(
    session: AsyncSession, idea_id: uuid.UUID, data: UnknownCreate, source: Source
) -> Unknown:
    """Add an open unknown (does not commit)."""
    unknown = Unknown(
        idea_id=idea_id, source=source, status=UnknownStatus.OPEN, **data.model_dump()
    )
    session.add(unknown)
    return unknown


async def create_unknown(session: AsyncSession, idea_id: uuid.UUID, data: UnknownCreate) -> Unknown:
    unknown = add_unknown(session, idea_id, data, Source.USER)
    await session.commit()
    await session.refresh(unknown)
    return unknown


async def update_unknown(session: AsyncSession, unknown: Unknown, data: UnknownUpdate) -> Unknown:
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(unknown, field, value)
    if changes.keys() & {"question", "category", "priority"}:
        unknown.source = Source.USER  # the user now owns its content
    await session.commit()
    await session.refresh(unknown)
    return unknown


# ---------- ICPs ----------


def _icp_from_fields(
    idea_id: uuid.UUID,
    *,
    name: str,
    company_type: str,
    size_min: int | None,
    size_max: int | None,
    geography: str,
    signals: list[str],
    user_roles: list[str],
    buyer_roles: list[str],
    ratings: dict[Criterion, Rating],
    source: Source,
    is_primary: bool,
) -> ICP:
    return ICP(
        idea_id=idea_id,
        name=name,
        company_type=company_type,
        size_min=size_min,
        size_max=size_max,
        geography=geography,
        signals=signals,
        roles={"users": user_roles, "buyers": buyer_roles},
        score_components={c.value: r.model_dump() for c, r in ratings.items()},
        hypothesis_score=compute_score(ratings),
        source=source,
        is_primary=is_primary,
        status=ICPStatus.ACTIVE,
    )


async def list_icps(
    session: AsyncSession, idea_id: uuid.UUID, include_dismissed: bool = False
) -> list[ICP]:
    query = select(ICP).where(ICP.idea_id == idea_id)
    if not include_dismissed:
        query = query.where(ICP.status == ICPStatus.ACTIVE)
    result = await session.scalars(
        query.order_by(ICP.is_primary.desc(), ICP.hypothesis_score.desc(), ICP.created_at)
    )
    return list(result)


async def get_icp(session: AsyncSession, idea_id: uuid.UUID, icp_id: uuid.UUID) -> ICP | None:
    return await session.scalar(select(ICP).where(ICP.id == icp_id, ICP.idea_id == idea_id))


async def _clear_primary(session: AsyncSession, idea_id: uuid.UUID) -> None:
    await session.execute(update(ICP).where(ICP.idea_id == idea_id).values(is_primary=False))


async def create_icp(session: AsyncSession, idea_id: uuid.UUID, data: ICPCreate) -> ICP:
    if data.is_primary:
        await _clear_primary(session, idea_id)
    icp = _icp_from_fields(
        idea_id,
        name=data.name,
        company_type=data.company_type,
        size_min=data.size_min,
        size_max=data.size_max,
        geography=data.geography,
        signals=data.signals,
        user_roles=data.user_roles,
        buyer_roles=data.buyer_roles,
        ratings=data.ratings.as_dict(),
        source=Source.USER,
        is_primary=data.is_primary,
    )
    session.add(icp)
    await session.commit()
    await session.refresh(icp)
    return icp


async def update_icp(session: AsyncSession, icp: ICP, data: ICPUpdate) -> ICP:
    changes = data.model_dump(exclude_unset=True)
    content_changed = False

    for field in ("name", "company_type", "size_min", "size_max", "geography", "signals"):
        if field in changes:
            setattr(icp, field, changes[field])
            content_changed = True
    if "user_roles" in changes or "buyer_roles" in changes:
        icp.roles = {
            "users": changes.get("user_roles", icp.roles.get("users", [])),
            "buyers": changes.get("buyer_roles", icp.roles.get("buyers", [])),
        }
        content_changed = True
    if data.ratings is not None:
        ratings = data.ratings.as_dict()
        icp.score_components = {c.value: r.model_dump() for c, r in ratings.items()}
        icp.hypothesis_score = compute_score(ratings)
        content_changed = True
    if content_changed:
        icp.source = Source.USER

    if "status" in changes:
        icp.status = changes["status"]
        if icp.status == ICPStatus.DISMISSED:
            icp.is_primary = False
    if changes.get("is_primary") is True and icp.status == ICPStatus.ACTIVE:
        await _clear_primary(session, icp.idea_id)
        icp.is_primary = True
    elif changes.get("is_primary") is False:
        icp.is_primary = False

    await session.commit()
    await session.refresh(icp)
    return icp
