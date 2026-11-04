"""Case-board aggregates. Reads only through other modules' service functions."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analysis import service as analysis
from app.modules.analysis.models import UnknownStatus
from app.modules.competitors import service as competitors
from app.modules.ideas import service as ideas
from app.modules.ideas.models import Idea
from app.modules.interviews import service as interviews
from app.modules.outreach import service as outreach
from app.modules.portfolio.schemas import EvidenceTally, Funnel, PortfolioItem, Validation
from app.modules.prospects import service as prospects
from app.modules.research import service as research
from app.modules.responses import service as responses
from app.modules.users.models import User
from app.modules.validation import service as validation
from app.modules.wtp import service as wtp


async def _item(session: AsyncSession, idea: Idea) -> PortfolioItem:
    evidence = await research.list_evidence(session, idea.id)
    tally = EvidenceTally()
    for e in evidence:
        setattr(tally, e["stance"].value, getattr(tally, e["stance"].value) + 1)
        setattr(tally, e["verification"].value, getattr(tally, e["verification"].value) + 1)

    unknowns = await analysis.list_unknowns(session, idea.id)
    hypothesis = await analysis.get_current_hypothesis(session, idea.id)
    rows = await prospects.list_prospects(session, idea.id)
    imports = await research.list_imports(session, idea.id)
    run = await analysis.latest_run(session, idea.id)

    stamps = [idea.updated_at]
    if imports:
        stamps.append(imports[0].created_at)
    if run is not None:
        stamps.append(run.created_at)
    if hypothesis is not None:
        stamps.append(hypothesis.created_at)

    busy = (run is not None and run.status in ("queued", "running")) or any(
        i.status in ("queued", "verifying") for i in imports
    )
    scores = [r["score"] for r in rows if r["score"] is not None]
    snap = await validation.latest(session, idea.id)
    commitments = await wtp.list_signals(session, idea.id)
    return PortfolioItem(
        id=idea.id,
        title=idea.title,
        target_market=idea.target_market,
        state=idea.state,
        problem=hypothesis.problem if hypothesis else None,
        evidence=tally,
        competitors=len(await competitors.list_competitors(session, idea.id)),
        prospects=len(rows),
        top_score=max(scores) if scores else None,
        unknowns_open=sum(u.status == UnknownStatus.OPEN for u in unknowns),
        unknowns_answered=sum(u.status == UnknownStatus.ANSWERED for u in unknowns),
        busy=busy,
        validation=Validation(
            score=snap.total,
            recommendation=snap.recommendation,
            headline=snap.decision["headline"],
            validated_conversations=snap.metrics["validated_conversations"],
            stale=snap.inputs_hash != await validation.current_hash(session, idea),
            computed_at=snap.created_at,
        )
        if snap
        else None,
        funnel=Funnel(
            sent=await outreach.sent_count(session, idea.id),
            replies=len(await responses.list_responses(session, idea.id)),
            interviews_done=await interviews.count_done(session, idea.id),
            pilot_or_better=sum(
                1 for s in commitments if s.commitment.value in ("pilot", "signed", "paid")
            ),
        ),
        created_at=idea.created_at,
        last_activity=max(stamps),
    )


async def portfolio(session: AsyncSession, user: User) -> list[PortfolioItem]:
    items = [await _item(session, idea) for idea in await ideas.list_ideas(session, user.id)]
    return sorted(items, key=lambda i: i.last_activity, reverse=True)
