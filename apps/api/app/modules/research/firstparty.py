"""First-party evidence (Phase 3): the customer's own words from a reply or interview.

Each item becomes `fact` evidence only if its quote is found verbatim in the text it came from
(the same matcher research uses). The full text is stored on an internal `preuve://` source, so
the quote stays verifiable and is deleted with it.
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.research.matching import match_quote, quote_key
from app.modules.research.models import (
    Evidence,
    EvidenceOrigin,
    EvidenceUnknown,
    FetchStatus,
    Verification,
    WebSource,
)
from app.modules.research.pack import EvidenceKind, Relevance, SourceType, Stance


@dataclass(frozen=True)
class Signal:
    """One extracted signal: what it says (statement) and the customer's exact words (quote)."""

    label: str  # e.g. "Frequency: weekly"
    quote: str
    stance: Stance = Stance.NEUTRAL
    relevance: Relevance = Relevance.HIGH


_WRAPPERS = "\"'“”‘’«»"


def clean_quote(quote: str) -> str:
    """Drop the quotation marks a model wraps around a quote ('like this'); the words inside
    are what must appear verbatim."""
    return quote.strip().strip(_WRAPPERS).strip()


def recover_quote(value: str, quote: str, text: str) -> str:
    """The model's quote (unwrapped); or, when it left the quote empty but its *value* is itself
    a verbatim span of the text (e.g. "every week"), that value. Anything else stays unquoted."""
    if clean_quote(quote):
        return clean_quote(quote)
    v = clean_quote(value)
    return v if v and match_quote(v, text).found else ""


def source_url(origin: EvidenceOrigin, owner_id: uuid.UUID) -> str:
    kind = "responses" if origin == EvidenceOrigin.REPLY else "interviews"
    return f"preuve://{kind}/{owner_id}"


async def clear(
    session: AsyncSession, idea_id: uuid.UUID, origin: EvidenceOrigin, owner_id: uuid.UUID
) -> None:
    """Delete the internal source of a reply/interview; its evidence goes with it (CASCADE),
    and so do reports that quoted that evidence (Phase 5B)."""
    from app.modules.reports import service as reports  # lazy: reports imports research

    ids = set(
        await session.scalars(
            select(Evidence.id)
            .join(WebSource, WebSource.id == Evidence.source_id)
            .where(WebSource.idea_id == idea_id, WebSource.url == source_url(origin, owner_id))
        )
    )
    await reports.forget_evidence(session, idea_id, {str(i) for i in ids})
    await session.execute(
        delete(WebSource).where(
            WebSource.idea_id == idea_id, WebSource.url == source_url(origin, owner_id)
        )
    )


async def record(
    session: AsyncSession,
    *,
    idea_id: uuid.UUID,
    origin: EvidenceOrigin,
    owner_id: uuid.UUID,
    title: str,
    text: str,
    at: datetime,
    signals: list[Signal],
    company_name: str | None = None,
) -> tuple[list[uuid.UUID], list[dict[str, Any]]]:
    """Replace this reply's/interview's evidence with the signals whose quotes verify.

    Returns (evidence ids, dropped signals with the reason). Does not commit.
    """
    await clear(session, idea_id, origin, owner_id)
    await session.flush()
    source = WebSource(
        idea_id=idea_id,
        url=source_url(origin, owner_id),
        title=title,
        fetched_at=at,
        fetch_status=FetchStatus.OK,
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
        text=text,
        full_text=text,
    )
    session.add(source)
    await session.flush()

    created: list[uuid.UUID] = []
    dropped: list[dict[str, Any]] = []
    seen: set[str] = set()
    prefix = "R" if origin == EvidenceOrigin.REPLY else "I"
    for sig in signals:
        quote = sig.quote.strip()
        result = match_quote(quote, text)
        if not result.found:
            dropped.append({"label": sig.label, "quote": quote, "reason": result.reason})
            continue
        key = quote_key(quote)
        if key in seen:  # several signals quoting the same words: keep the first
            continue
        seen.add(key)
        ev = Evidence(
            idea_id=idea_id,
            import_id=None,
            source_id=source.id,
            origin=origin,
            response_id=owner_id if origin == EvidenceOrigin.REPLY else None,
            interview_id=owner_id if origin == EvidenceOrigin.INTERVIEW else None,
            ref=f"{prefix}-{len(created) + 1}",
            quote=quote,
            quote_key=key,
            statement=sig.label,
            source_type=SourceType.OTHER,
            kind=EvidenceKind.FACT,
            stance=sig.stance,
            relevance=sig.relevance,
            company_name=company_name,
            published_at=at.date(),
            verification=Verification.VERIFIED,
            verification_note=f"Quote found verbatim in the {origin.value}.",
        )
        session.add(ev)
        await session.flush()
        created.append(ev.id)
    return created, dropped


async def link_unknown(
    session: AsyncSession, evidence_ids: list[uuid.UUID], unknown_id: uuid.UUID
) -> None:
    linked = set(
        await session.scalars(
            select(EvidenceUnknown.evidence_id).where(
                EvidenceUnknown.unknown_id == unknown_id,
                EvidenceUnknown.evidence_id.in_(evidence_ids),
            )
        )
    )
    for eid in evidence_ids:
        if eid not in linked:
            session.add(EvidenceUnknown(evidence_id=eid, unknown_id=unknown_id))
    await session.flush()
