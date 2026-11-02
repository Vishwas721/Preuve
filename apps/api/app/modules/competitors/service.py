import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analysis.models import Source
from app.modules.competitors.models import Competitor, CompetitorEvidence, CompetitorStatus
from app.modules.competitors.schemas import (
    CompetitorCreate,
    CompetitorUpdate,
    ResearchCompetitorInput,
)
from app.modules.research.pack import name_key

CONTENT_FIELDS = ("name", "kind", "url", "description", "pricing_note")


class DuplicateCompetitorError(Exception):
    pass


async def _by_key(session: AsyncSession, idea_id: uuid.UUID, key: str) -> Competitor | None:
    return await session.scalar(
        select(Competitor).where(Competitor.idea_id == idea_id, Competitor.name_key == key)
    )


async def _link_evidence(
    session: AsyncSession, competitor_id: uuid.UUID, evidence_ids: list[uuid.UUID]
) -> None:
    existing = set(
        await session.scalars(
            select(CompetitorEvidence.evidence_id).where(
                CompetitorEvidence.competitor_id == competitor_id
            )
        )
    )
    for eid in dict.fromkeys(evidence_ids):
        if eid not in existing:
            session.add(CompetitorEvidence(competitor_id=competitor_id, evidence_id=eid))


async def upsert_from_research(
    session: AsyncSession,
    idea_id: uuid.UUID,
    import_id: uuid.UUID,
    items: list[ResearchCompetitorInput],
) -> dict[str, list[str]]:
    """Merge verified competitors by normalized name (does not commit).

    New names are created with source `research`. For existing entries, evidence links are always
    added. Research text is refreshed only if the user hasn't edited the entry, and a dismissed
    entry stays dismissed.
    """
    created, updated = [], []
    for item in items:
        comp = await _by_key(session, idea_id, name_key(item.name))
        if comp is None:
            comp = Competitor(
                idea_id=idea_id,
                name=item.name,
                name_key=name_key(item.name),
                url=item.url,
                kind=item.kind,
                description=item.description,
                pricing_note=item.pricing_note,
                sentiment=item.sentiment,
                source=Source.RESEARCH,
                status=CompetitorStatus.ACTIVE,
            )
            session.add(comp)
            created.append(item.name)
        else:
            if not comp.user_edited:
                comp.url = item.url or comp.url
                comp.kind = item.kind
                comp.description = item.description
                comp.pricing_note = item.pricing_note or comp.pricing_note
                if item.sentiment:
                    comp.sentiment = item.sentiment
            updated.append(comp.name)
        comp.last_import_id = import_id
        await session.flush()
        await _link_evidence(session, comp.id, item.evidence_ids)
    await session.flush()
    return {"created": created, "updated": updated}


async def list_competitors(
    session: AsyncSession, idea_id: uuid.UUID, include_dismissed: bool = False
) -> list[dict[str, Any]]:
    query = select(Competitor).where(Competitor.idea_id == idea_id)
    if not include_dismissed:
        query = query.where(Competitor.status == CompetitorStatus.ACTIVE)
    comps = list(await session.scalars(query.order_by(Competitor.kind, Competitor.name)))

    links: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    if comps:
        for link in await session.scalars(
            select(CompetitorEvidence).where(
                CompetitorEvidence.competitor_id.in_([c.id for c in comps])
            )
        ):
            links[link.competitor_id].append(link.evidence_id)

    return [
        {
            **{
                f: getattr(c, f)
                for f in (
                    "id",
                    "name",
                    "url",
                    "kind",
                    "description",
                    "pricing_note",
                    "sentiment",
                    "source",
                    "status",
                    "user_edited",
                    "created_at",
                    "updated_at",
                )
            },
            "evidence_ids": links[c.id],
        }
        for c in comps
    ]


async def get_competitor(
    session: AsyncSession, idea_id: uuid.UUID, competitor_id: uuid.UUID
) -> Competitor | None:
    return await session.scalar(
        select(Competitor).where(Competitor.id == competitor_id, Competitor.idea_id == idea_id)
    )


async def create_competitor(
    session: AsyncSession, idea_id: uuid.UUID, data: CompetitorCreate
) -> Competitor:
    key = name_key(data.name)
    if await _by_key(session, idea_id, key) is not None:
        raise DuplicateCompetitorError(f"'{data.name}' is already listed")
    comp = Competitor(
        idea_id=idea_id,
        name_key=key,
        source=Source.USER,
        status=CompetitorStatus.ACTIVE,
        sentiment=[],
        user_edited=True,
        **data.model_dump(),
    )
    session.add(comp)
    await session.commit()
    await session.refresh(comp)
    return comp


async def update_competitor(
    session: AsyncSession, comp: Competitor, data: CompetitorUpdate
) -> Competitor:
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes:
        key = name_key(changes["name"])
        other = await _by_key(session, comp.idea_id, key)
        if other is not None and other.id != comp.id:
            raise DuplicateCompetitorError(f"'{changes['name']}' is already listed")
        comp.name_key = key
    for f, value in changes.items():
        setattr(comp, f, value)
    if changes.keys() & set(CONTENT_FIELDS):
        comp.user_edited = True
    await session.commit()
    await session.refresh(comp)
    return comp
