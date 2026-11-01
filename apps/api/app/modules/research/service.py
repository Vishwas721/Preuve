import asyncio
import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.guardrails import Claim
from app.modules.analysis import service as analysis
from app.modules.analysis.models import Source, Unknown
from app.modules.analysis.schemas import UnknownCreate
from app.modules.ideas.models import Idea
from app.modules.research.matching import match_any, quote_key
from app.modules.research.models import (
    Evidence,
    EvidenceUnknown,
    FetchStatus,
    ImportStatus,
    ResearchImport,
    UnknownFinding,
    Verification,
    WebSource,
)
from app.modules.research.pack import FindingStatus, ResearchPack
from app.modules.research.schemas import EvidenceUpdate
from app.search.fetch import FetchedPage, FetchError

logger = logging.getLogger(__name__)

FETCH_CONCURRENCY = 4
POLITENESS_DELAY_S = 0.5  # pause after each request to the same host


class Fetcher(Protocol):
    async def fetch(self, url: str) -> FetchedPage: ...


def _now() -> datetime:
    return datetime.now(UTC)


# ---------- creating an import ----------


async def validate_for_idea(session: AsyncSession, idea: Idea, pack: ResearchPack) -> list[str]:
    """Checks that need the database (the schema itself is validated by Pydantic)."""
    errors: list[str] = []
    if pack.meta.idea_id != idea.id:
        errors.append(f"meta.idea_id {pack.meta.idea_id} does not match idea {idea.id}")
    referenced = {u for e in pack.evidence for u in e.unknown_ids} | {
        f.unknown_id for f in pack.unknown_findings
    }
    if referenced:
        found = set(
            await session.scalars(
                select(Unknown.id).where(Unknown.idea_id == idea.id, Unknown.id.in_(referenced))
            )
        )
        missing = sorted(str(u) for u in referenced - found)
        if missing:
            errors.append(f"unknown ids not found on this idea: {missing}")
    return errors


async def create_import(session: AsyncSession, idea: Idea, pack: ResearchPack) -> ResearchImport:
    imp = ResearchImport(
        idea_id=idea.id,
        schema_version=pack.meta.schema_version,
        method_version=pack.meta.method_version,
        researcher=pack.meta.researcher,
        pack=pack.model_dump(mode="json"),
        status=ImportStatus.QUEUED,
        report={},
    )
    session.add(imp)
    await session.commit()
    await session.refresh(imp)
    return imp


async def fail_import(session: AsyncSession, imp: ResearchImport, error: str) -> None:
    imp.status = ImportStatus.FAILED
    imp.error = error[:2000]
    imp.finished_at = _now()
    await session.commit()


async def fail_if_active(session: AsyncSession, import_id: uuid.UUID, error: str) -> None:
    imp = await session.get(ResearchImport, import_id)
    if imp is not None and imp.status in (ImportStatus.QUEUED, ImportStatus.VERIFYING):
        await fail_import(session, imp, error)


# ---------- verification ----------


async def _fetch_all(
    fetcher: Fetcher, urls: list[str], delay: float
) -> dict[str, FetchedPage | str]:
    """Fetch each URL once: bounded concurrency, one request at a time per host."""
    sem = asyncio.Semaphore(FETCH_CONCURRENCY)
    host_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def one(url: str) -> tuple[str, FetchedPage | str]:
        async with sem, host_locks[urlsplit(url).netloc]:
            try:
                result: FetchedPage | str = await fetcher.fetch(url)
            except FetchError as exc:
                result = str(exc)
            except Exception as exc:  # never let one bad page fail the import
                result = f"Fetch failed: {exc!r}"
            if delay:
                await asyncio.sleep(delay)
            return url, result

    return dict(await asyncio.gather(*(one(u) for u in urls)))


async def _upsert_source(
    session: AsyncSession, idea_id: uuid.UUID, url: str, page: FetchedPage | str
) -> WebSource:
    src = await session.scalar(
        select(WebSource).where(WebSource.idea_id == idea_id, WebSource.url == url)
    )
    if src is None:
        src = WebSource(idea_id=idea_id, url=url)
        session.add(src)
    if isinstance(page, FetchedPage):
        src.final_url = page.final_url
        src.title = page.title
        src.fetched_at = page.fetched_at
        src.fetch_status = FetchStatus.OK
        src.fetch_note = None
        src.content_hash = page.content_hash
        src.text = page.text
        src.full_text = page.full_text
    else:  # keep any text from an earlier successful fetch for audit
        src.fetched_at = _now()
        src.fetch_status = FetchStatus.FAILED
        src.fetch_note = page[:1000]
    await session.flush()
    return src


async def _link_unknowns(
    session: AsyncSession, evidence_id: uuid.UUID, unknown_ids: list[uuid.UUID]
) -> None:
    existing = set(
        await session.scalars(
            select(EvidenceUnknown.unknown_id).where(EvidenceUnknown.evidence_id == evidence_id)
        )
    )
    for uid in set(unknown_ids) - existing:
        session.add(EvidenceUnknown(evidence_id=evidence_id, unknown_id=uid))


def _remap_claims(
    claims: list[Claim], ref_map: dict[str, uuid.UUID]
) -> tuple[list[dict], list[dict]]:
    """Keep claims whose every cited ref was stored; rewrite refs to evidence ids."""
    kept, dropped = [], []
    for c in claims:
        missing = [r for r in c.evidence_ids if r not in ref_map]
        if missing:
            dropped.append({"statement": c.statement, "missing_refs": missing})
        else:
            data = c.model_dump(mode="json")
            data["evidence_ids"] = [str(ref_map[r]) for r in c.evidence_ids]
            kept.append(data)
    return kept, dropped


async def verify_import(
    session: AsyncSession,
    fetcher: Fetcher,
    import_id: uuid.UUID,
    *,
    delay: float = POLITENESS_DELAY_S,
) -> ImportStatus:
    imp = await session.get(ResearchImport, import_id)
    if imp is None:
        raise ValueError(f"Research import {import_id} not found")
    imp.status = ImportStatus.VERIFYING
    imp.started_at = _now()
    await session.commit()

    try:
        report = await _verify(session, fetcher, imp, delay)
    except Exception as exc:
        logger.exception("research import %s failed", import_id)
        await session.rollback()
        await session.refresh(imp)
        await fail_import(session, imp, f"Verification failed: {exc}")
        return imp.status

    imp.report = report
    imp.status = ImportStatus.DONE
    imp.finished_at = _now()
    await session.commit()
    return imp.status


async def _verify(
    session: AsyncSession, fetcher: Fetcher, imp: ResearchImport, delay: float
) -> dict[str, Any]:
    pack = ResearchPack.model_validate(imp.pack)
    idea_id = imp.idea_id

    urls = list(dict.fromkeys(e.url for e in pack.evidence))
    pages = await _fetch_all(fetcher, urls, delay)
    sources = {url: await _upsert_source(session, idea_id, url, pages[url]) for url in urls}

    ref_map: dict[str, uuid.UUID] = {}
    rejected: list[dict] = []
    duplicates: list[str] = []
    counts = {"verified": 0, "unverifiable": 0, "rejected": 0}

    for item in pack.evidence:
        page = pages[item.url]
        if isinstance(page, FetchedPage):
            match = match_any(item.quote, page.text, page.full_text)
            if not match.found:
                rejected.append({"ref": item.ref, "url": item.url, "reason": match.reason})
                counts["rejected"] += 1
                continue
            verification, note = Verification.VERIFIED, None
        else:
            verification, note = Verification.UNVERIFIABLE, page

        source = sources[item.url]
        key = quote_key(item.quote)
        evidence = await session.scalar(
            select(Evidence).where(
                Evidence.idea_id == idea_id,
                Evidence.source_id == source.id,
                Evidence.quote_key == key,
            )
        )
        if evidence is not None:
            duplicates.append(item.ref)
            if verification == Verification.VERIFIED:  # a re-check can upgrade, never downgrade
                evidence.verification, evidence.verification_note = verification, None
        else:
            evidence = Evidence(
                idea_id=idea_id,
                import_id=imp.id,
                source_id=source.id,
                ref=item.ref,
                quote=item.quote,
                quote_key=key,
                statement=item.statement,
                source_type=item.source_type,
                kind=item.kind,
                stance=item.stance,
                relevance=item.relevance,
                company_name=item.company_name,
                published_at=item.published_at,
                verification=verification,
                verification_note=note,
            )
            session.add(evidence)
            await session.flush()
        await _link_unknowns(session, evidence.id, item.unknown_ids)
        ref_map[item.ref] = evidence.id
        counts[evidence.verification.value] += 1

    dropped_claims: list[dict] = []
    downgraded: list[str] = []
    for f in pack.unknown_findings:
        kept, dropped = _remap_claims(f.summary, ref_map)
        dropped_claims += [d | {"unknown_id": str(f.unknown_id)} for d in dropped]
        status = f.status
        if status != FindingStatus.NO_EVIDENCE_FOUND and not kept:
            status = FindingStatus.NO_EVIDENCE_FOUND
            downgraded.append(str(f.unknown_id))
        session.add(
            UnknownFinding(unknown_id=f.unknown_id, import_id=imp.id, status=status, summary=kept)
        )

    hypothesis_version = None
    hypothesis_skipped = None
    if pack.hypothesis_update is not None:
        kept, dropped = _remap_claims(pack.hypothesis_update.rationale, ref_map)
        dropped_claims += [d | {"hypothesis": True} for d in dropped]
        if kept:
            fields = pack.hypothesis_update.model_dump(exclude={"rationale"})
            reasons = "; ".join(c["statement"] for c in kept)
            hyp = await analysis.add_hypothesis_version(
                session,
                idea_id,
                fields,
                Source.RESEARCH,
                f"From research (method v{pack.meta.method_version}): {reasons}"[:2000],
            )
            hypothesis_version = hyp.version
        else:
            hypothesis_skipped = "every rationale claim cited rejected or missing evidence"

    for nu in pack.new_unknowns:
        analysis.add_unknown(session, idea_id, UnknownCreate(**nu.model_dump()), Source.RESEARCH)

    await session.flush()
    return {
        "counts": counts,
        "rejected": rejected,
        "duplicates": duplicates,
        "dropped_claims": dropped_claims,
        "downgraded_findings": downgraded,
        "hypothesis_version": hypothesis_version,
        "hypothesis_skipped": hypothesis_skipped,
        "new_unknowns": len(pack.new_unknowns),
        "sources": {
            "fetched": sum(isinstance(p, FetchedPage) for p in pages.values()),
            "failed": sum(not isinstance(p, FetchedPage) for p in pages.values()),
        },
    }


# ---------- reading ----------


async def list_imports(session: AsyncSession, idea_id: uuid.UUID) -> list[ResearchImport]:
    result = await session.scalars(
        select(ResearchImport)
        .where(ResearchImport.idea_id == idea_id)
        .order_by(ResearchImport.created_at.desc())
    )
    return list(result)


async def get_import(
    session: AsyncSession, idea_id: uuid.UUID, import_id: uuid.UUID
) -> ResearchImport | None:
    return await session.scalar(
        select(ResearchImport).where(
            ResearchImport.id == import_id, ResearchImport.idea_id == idea_id
        )
    )


async def list_evidence(
    session: AsyncSession,
    idea_id: uuid.UUID,
    *,
    include_dismissed: bool = False,
    unknown_id: uuid.UUID | None = None,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Evidence rows joined with their source and linked unknowns, ready for `EvidenceRead`."""
    query = (
        select(Evidence, WebSource)
        .join(WebSource, Evidence.source_id == WebSource.id)
        .where(Evidence.idea_id == idea_id)
    )
    if not include_dismissed:
        query = query.where(Evidence.dismissed.is_(False))
    for field, value in (filters or {}).items():
        if value is not None:
            query = query.where(getattr(Evidence, field) == value)
    if unknown_id is not None:
        query = query.join(EvidenceUnknown, EvidenceUnknown.evidence_id == Evidence.id).where(
            EvidenceUnknown.unknown_id == unknown_id
        )
    rows = (await session.execute(query.order_by(Evidence.created_at))).all()

    ids = [e.id for e, _ in rows]
    links: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    if ids:
        for link in await session.scalars(
            select(EvidenceUnknown).where(EvidenceUnknown.evidence_id.in_(ids))
        ):
            links[link.evidence_id].append(link.unknown_id)

    return [
        {
            **{
                c: getattr(e, c)
                for c in (
                    "id",
                    "import_id",
                    "ref",
                    "quote",
                    "statement",
                    "source_type",
                    "kind",
                    "stance",
                    "relevance",
                    "company_name",
                    "published_at",
                    "verification",
                    "verification_note",
                    "dismissed",
                    "user_edited",
                    "original_labels",
                    "created_at",
                )
            },
            "url": src.url,
            "final_url": src.final_url,
            "title": src.title,
            "fetched_at": src.fetched_at,
            "unknown_ids": links[e.id],
        }
        for e, src in rows
    ]


async def latest_findings(session: AsyncSession, idea_id: uuid.UUID) -> list[UnknownFinding]:
    """The most recent finding per unknown of this idea."""
    rows = await session.scalars(
        select(UnknownFinding)
        .join(Unknown, Unknown.id == UnknownFinding.unknown_id)
        .where(Unknown.idea_id == idea_id)
        .order_by(UnknownFinding.unknown_id, UnknownFinding.created_at.desc())
    )
    latest: dict[uuid.UUID, UnknownFinding] = {}
    for f in rows:
        latest.setdefault(f.unknown_id, f)
    return list(latest.values())


async def get_evidence(
    session: AsyncSession, idea_id: uuid.UUID, evidence_id: uuid.UUID
) -> Evidence | None:
    return await session.scalar(
        select(Evidence).where(Evidence.id == evidence_id, Evidence.idea_id == idea_id)
    )


async def update_evidence(session: AsyncSession, evidence: Evidence, data: EvidenceUpdate) -> None:
    changes = data.model_dump(exclude_unset=True)
    labels = {k: v for k, v in changes.items() if k in ("kind", "stance", "relevance")}
    if labels and not evidence.user_edited:
        evidence.original_labels = {
            "kind": evidence.kind.value,
            "stance": evidence.stance.value,
            "relevance": evidence.relevance.value,
        }
    for field, value in changes.items():
        setattr(evidence, field, value)
    if labels:
        evidence.user_edited = True
    await session.commit()
