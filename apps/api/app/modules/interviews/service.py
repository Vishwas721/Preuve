"""Interviews (PRD §21–§22). Notes are private: extraction runs with `private=True`."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.interviews.models import Interview, InterviewStatus
from app.modules.research import firstparty
from app.modules.research.models import EvidenceOrigin
from app.modules.wtp import service as wtp


async def count_done(session: AsyncSession, idea_id: uuid.UUID) -> int:
    return (
        await session.scalar(
            select(func.count()).where(
                Interview.idea_id == idea_id, Interview.status == InterviewStatus.DONE
            )
        )
        or 0
    )


async def _drop(session: AsyncSession, rows: list[Interview]) -> None:
    for row in rows:
        await firstparty.clear(session, row.idea_id, EvidenceOrigin.INTERVIEW, row.id)
        await wtp.forget_interview(session, row.id)
        await session.delete(row)  # notes cascade
    await session.flush()


async def forget_contact(session: AsyncSession, contact_id: uuid.UUID) -> None:
    """Deletion request (PRD §37): delete this person's interviews, notes and their evidence."""
    await _drop(
        session,
        list(await session.scalars(select(Interview).where(Interview.contact_id == contact_id))),
    )
