"""Experiments: cohort results counted from sent messages, replies and interviews (PRD §28)."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analysis import service as analysis
from app.modules.experiments.models import Experiment, ExperimentStatus
from app.modules.experiments.schemas import Cohort, ExperimentCreate, ExperimentUpdate
from app.modules.interviews import service as interviews
from app.modules.outreach import service as outreach
from app.modules.prospects import service as prospects
from app.modules.responses import service as responses

MIN_SAMPLE = 10  # sent messages per cohort before a comparison means much


class ExperimentError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _norm(text: str | None) -> str:
    return " ".join((text or "").lower().split())


async def _check_cohort(session: AsyncSession, idea_id: uuid.UUID, cohort: Cohort | None) -> None:
    if cohort is None:
        return
    campaigns = {c.id for c in await outreach.list_campaigns(session, idea_id)}
    unknown = [str(c) for c in cohort.campaign_ids if c not in campaigns]
    if unknown:
        raise ExperimentError(f"Unknown campaign(s) for this idea: {', '.join(unknown)}")
    if (
        cohort.icp_id is not None
        and await analysis.get_icp(session, idea_id, cohort.icp_id) is None
    ):
        raise ExperimentError("Unknown ICP for this idea.")


def _ratio(a: int, b: int) -> float | None:
    return round(a / b, 3) if b else None


async def _results(session: AsyncSession, idea_id: uuid.UUID, cohorts: list[Cohort]) -> list[dict]:
    sent = await outreach.sent_with_campaigns(session, idea_id)
    roles = {c.id: c.role for c, _ in await prospects.list_idea_contacts(session, idea_id)}
    replies = await responses.list_responses(session, idea_id)
    done = [i for i in await interviews.list_interviews(session, idea_id) if i.status == "done"]

    out = []
    for cohort in cohorts:
        role = _norm(cohort.role_contains)
        messages = [
            m
            for m, camp in sent
            if (not cohort.campaign_ids or camp.id in cohort.campaign_ids)
            and (cohort.icp_id is None or camp.icp_id == cohort.icp_id)
            and (not role or role in _norm(roles.get(m.contact_id, "")))
        ]
        ids = {m.id for m in messages}
        contacts = {m.contact_id for m in messages if m.contact_id}
        got = [r for r in replies if r.message_id in ids]
        replied = {r.message_id for r in got}
        classified = [r.classification for r in got if r.classification]

        def label(c: dict[str, Any], field: str) -> str:
            v = c.get(field)
            return str(v.get("value", "")) if isinstance(v, dict) else str(v or "")

        reply_ids = {r.id for r in got}
        out.append(
            {
                "label": cohort.label,
                "sent": len(messages),
                "replies": len(replied),
                "reply_rate": _ratio(len(replied), len(messages)),
                "positive": sum(1 for c in classified if label(c, "sentiment") == "positive"),
                "problem_confirmed": sum(
                    1 for c in classified if label(c, "problem_confirmed") == "yes"
                ),
                "interview_recommended": sum(
                    1 for c in classified if label(c, "recommended_action") == "interview"
                ),
                "interviews_done": sum(
                    1 for i in done if i.contact_id in contacts or i.response_id in reply_ids
                ),
                "small_sample": len(messages) < MIN_SAMPLE,
            }
        )
    return out


def _compare(a: dict, b: dict | None) -> list[str]:
    """Counts side by side. No interpretation: the user writes the conclusion."""
    if b is None:
        return []
    lines = []
    for key, name in (
        ("replies", "Replies"),
        ("positive", "Positive replies"),
        ("problem_confirmed", "Problem confirmed"),
        ("interviews_done", "Interviews done"),
    ):
        lines.append(
            f"{name}: {a['label']} {a[key]}/{a['sent']}, {b['label']} {b[key]}/{b['sent']}."
        )
    small = [x["label"] for x in (a, b) if x["small_sample"]]
    if small:
        lines.append(
            f"Sample too small (under {MIN_SAMPLE} sent): {', '.join(small)}. "
            "Treat differences as anecdotes."
        )
    return lines


async def compute(session: AsyncSession, row: Experiment) -> dict:
    cohorts = [Cohort.model_validate(row.cohort_a)]
    if row.cohort_b:
        cohorts.append(Cohort.model_validate(row.cohort_b))
    res = await _results(session, row.idea_id, cohorts)
    a, b = res[0], (res[1] if len(res) > 1 else None)
    return {"a": a, "b": b, "comparison": _compare(a, b), "computed_at": _now()}


async def result(session: AsyncSession, row: Experiment) -> dict:
    """Frozen once concluded; live while running."""
    return (
        row.result
        if row.status == ExperimentStatus.CONCLUDED and row.result
        else await compute(session, row)
    )


async def create(session: AsyncSession, idea_id: uuid.UUID, data: ExperimentCreate) -> Experiment:
    await _check_cohort(session, idea_id, data.cohort_a)
    await _check_cohort(session, idea_id, data.cohort_b)
    row = Experiment(
        idea_id=idea_id,
        hypothesis=data.hypothesis.strip(),
        cohort_a=data.cohort_a.model_dump(mode="json"),
        cohort_b=data.cohort_b.model_dump(mode="json") if data.cohort_b else None,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def update(session: AsyncSession, row: Experiment, data: ExperimentUpdate) -> Experiment:
    changes = data.model_dump(exclude_unset=True)
    if row.status == ExperimentStatus.CONCLUDED and (
        {"cohort_a", "cohort_b", "hypothesis"} & set(changes)
    ):
        raise ExperimentError("A concluded experiment can't change its hypothesis or cohorts.")
    for key in ("cohort_a", "cohort_b"):
        if key in changes:
            cohort = getattr(data, key)
            await _check_cohort(session, row.idea_id, cohort)
            setattr(row, key, cohort.model_dump(mode="json") if cohort else None)
    if data.hypothesis is not None:
        row.hypothesis = data.hypothesis.strip()
    if data.conclusion is not None:
        row.conclusion = data.conclusion.strip()
    if data.status is not None and data.status != row.status:
        if data.status == ExperimentStatus.CONCLUDED:
            if not row.conclusion:
                raise ExperimentError("Write a conclusion before concluding the experiment.")
            row.result = _jsonable(await compute(session, row))
            row.concluded_at = _now()
        else:  # reopened: results go live again
            row.result, row.concluded_at = None, None
        row.status = data.status
    await session.commit()
    await session.refresh(row)
    return row


def _jsonable(res: dict) -> dict:
    return {**res, "computed_at": res["computed_at"].isoformat()}


async def list_experiments(session: AsyncSession, idea_id: uuid.UUID) -> list[Experiment]:
    return list(
        await session.scalars(
            select(Experiment)
            .where(Experiment.idea_id == idea_id)
            .order_by(Experiment.created_at.desc())
        )
    )


async def get_experiment(
    session: AsyncSession, idea_id: uuid.UUID, experiment_id: uuid.UUID
) -> Experiment | None:
    row = await session.get(Experiment, experiment_id)
    return row if row is not None and row.idea_id == idea_id else None


async def delete(session: AsyncSession, row: Experiment) -> None:
    await session.delete(row)
    await session.commit()


async def read(session: AsyncSession, row: Experiment) -> dict:
    return {
        **{
            k: getattr(row, k)
            for k in (
                "id",
                "idea_id",
                "hypothesis",
                "cohort_a",
                "cohort_b",
                "status",
                "conclusion",
                "concluded_at",
                "created_at",
            )
        },
        "result": await result(session, row),
    }
