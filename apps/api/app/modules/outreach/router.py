import html
import logging
import uuid

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse

from app.core.config import get_settings
from app.core.deps import SessionDep
from app.email import get_email_provider
from app.modules.ideas.deps import OwnedIdea
from app.modules.outreach import safety, service
from app.modules.outreach.models import Message, OutreachCampaign, SuppressionReason
from app.modules.outreach.schemas import (
    CampaignCreate,
    CampaignRead,
    CampaignStats,
    CampaignUpdate,
    DraftRequest,
    DraftResult,
    MessageRead,
    MessageSummary,
    MessageUpdate,
    OutreachSettings,
    Recipient,
    SendQueued,
    SendRequest,
    SuppressionCreate,
    SuppressionRead,
)
from app.workers.queue import QueueDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ideas/{idea_id}", tags=["outreach"])
global_router = APIRouter(tags=["outreach"])
public_router = APIRouter(tags=["public"])

_UNAVAILABLE = "Job queue unavailable, try again shortly"


def _conflict(exc: Exception) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, str(exc))


async def _campaign_read(session: SessionDep, campaign: OutreachCampaign) -> CampaignRead:
    await session.refresh(campaign)
    stats = (await service.campaign_stats(session, [campaign.id])).get(campaign.id, {})
    return CampaignRead.model_validate(
        {**{c.key: getattr(campaign, c.key) for c in campaign.__table__.columns}}
        | {"stats": CampaignStats(**stats)}
    )


async def _owned_campaign(
    session: SessionDep, idea_id: uuid.UUID, campaign_id: uuid.UUID
) -> OutreachCampaign:
    campaign = await service.get_campaign(session, idea_id, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    return campaign


async def _owned_message(session: SessionDep, idea_id: uuid.UUID, message_id: uuid.UUID) -> Message:
    message = await service.get_message(session, idea_id, message_id)
    if message is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")
    return message


# ---------- campaigns ----------


@router.get("/campaigns", response_model=list[CampaignRead])
async def list_campaigns(idea: OwnedIdea, session: SessionDep) -> list[CampaignRead]:
    campaigns = await service.list_campaigns(session, idea.id)
    stats = await service.campaign_stats(session, [c.id for c in campaigns])
    return [
        CampaignRead.model_validate(
            {c.key: getattr(camp, c.key) for c in camp.__table__.columns}
            | {"stats": CampaignStats(**stats.get(camp.id, {}))}
        )
        for camp in campaigns
    ]


@router.post("/campaigns", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    idea: OwnedIdea, data: CampaignCreate, session: SessionDep
) -> CampaignRead:
    try:
        campaign = await service.create_campaign(session, idea, data)
    except service.OutreachError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return await _campaign_read(session, campaign)


@router.get("/campaigns/{campaign_id}", response_model=CampaignRead)
async def get_campaign(
    idea: OwnedIdea, campaign_id: uuid.UUID, session: SessionDep
) -> CampaignRead:
    return await _campaign_read(session, await _owned_campaign(session, idea.id, campaign_id))


@router.patch("/campaigns/{campaign_id}", response_model=CampaignRead)
async def update_campaign(
    idea: OwnedIdea, campaign_id: uuid.UUID, data: CampaignUpdate, session: SessionDep
) -> CampaignRead:
    campaign = await _owned_campaign(session, idea.id, campaign_id)
    await service.update_campaign(session, campaign, data)
    return await _campaign_read(session, campaign)


@router.get("/outreach/recipients", response_model=list[Recipient])
async def list_recipients(idea: OwnedIdea, session: SessionDep) -> list[dict]:
    return await service.list_recipients(session, idea.id)


# ---------- drafts ----------


@router.post(
    "/campaigns/{campaign_id}/drafts",
    response_model=DraftResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_drafts(
    idea: OwnedIdea,
    campaign_id: uuid.UUID,
    data: DraftRequest,
    session: SessionDep,
    queue: QueueDep,
) -> DraftResult:
    """Create one draft per contact and queue the drafting job."""
    campaign = await _owned_campaign(session, idea.id, campaign_id)
    created, skipped = await service.create_drafts(session, campaign, data.contact_ids)
    ids = [m.id for m in created]
    if ids:
        try:
            await queue.enqueue_job("draft_outreach", [str(i) for i in ids])
        except Exception as exc:
            logger.exception("could not enqueue draft_outreach")
            await service.mark_draft_failed(
                session, ids, "Could not reach the job queue (is Redis running?). Redraft later."
            )
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _UNAVAILABLE) from exc
    return DraftResult(created=ids, skipped=skipped)


@router.get("/campaigns/{campaign_id}/messages", response_model=list[MessageSummary])
async def list_messages(idea: OwnedIdea, campaign_id: uuid.UUID, session: SessionDep) -> list:
    campaign = await _owned_campaign(session, idea.id, campaign_id)
    return await service.list_messages(session, campaign.id)


@router.get("/messages/{message_id}", response_model=MessageRead)
async def get_message(idea: OwnedIdea, message_id: uuid.UUID, session: SessionDep) -> dict:
    message = await _owned_message(session, idea.id, message_id)
    return await service.message_detail(session, message)


@router.patch("/messages/{message_id}", response_model=MessageRead)
async def update_message(
    idea: OwnedIdea, message_id: uuid.UUID, data: MessageUpdate, session: SessionDep
) -> dict:
    message = await _owned_message(session, idea.id, message_id)
    try:
        await service.update_message(session, message, data)
    except service.OutreachError as exc:
        raise _conflict(exc) from exc
    return await service.message_detail(session, message)


async def _transition(session: SessionDep, idea_id: uuid.UUID, message_id: uuid.UUID, fn) -> dict:
    message = await _owned_message(session, idea_id, message_id)
    try:
        await fn(session, message)
    except service.OutreachError as exc:
        raise _conflict(exc) from exc
    return await service.message_detail(session, message)


@router.post("/messages/{message_id}/approve", response_model=MessageRead)
async def approve(idea: OwnedIdea, message_id: uuid.UUID, session: SessionDep) -> dict:
    return await _transition(session, idea.id, message_id, service.approve)


@router.post("/messages/{message_id}/reject", response_model=MessageRead)
async def reject(idea: OwnedIdea, message_id: uuid.UUID, session: SessionDep) -> dict:
    return await _transition(session, idea.id, message_id, service.reject)


@router.post("/messages/{message_id}/reopen", response_model=MessageRead)
async def reopen(idea: OwnedIdea, message_id: uuid.UUID, session: SessionDep) -> dict:
    return await _transition(session, idea.id, message_id, service.reopen)


@router.post("/messages/{message_id}/bounce", response_model=MessageRead)
async def mark_bounced(idea: OwnedIdea, message_id: uuid.UUID, session: SessionDep) -> dict:
    """Record a bounce that arrived later by email (suppresses the address)."""
    return await _transition(session, idea.id, message_id, service.mark_bounced)


@router.post("/messages/{message_id}/redraft", response_model=MessageRead)
async def redraft(
    idea: OwnedIdea, message_id: uuid.UUID, session: SessionDep, queue: QueueDep
) -> dict:
    message = await _owned_message(session, idea.id, message_id)
    try:
        await service.start_redraft(session, message)
    except service.OutreachError as exc:
        raise _conflict(exc) from exc
    try:
        await queue.enqueue_job("draft_outreach", [str(message.id)])
    except Exception as exc:
        await service.mark_draft_failed(session, [message.id], "Could not reach the job queue.")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _UNAVAILABLE) from exc
    return await service.message_detail(session, message)


# ---------- sending ----------


@router.post(
    "/campaigns/{campaign_id}/send",
    response_model=SendQueued,
    status_code=status.HTTP_202_ACCEPTED,
)
async def send(
    idea: OwnedIdea,
    campaign_id: uuid.UUID,
    data: SendRequest,
    session: SessionDep,
    queue: QueueDep,
) -> SendQueued:
    """Queue approved messages for sending; the job re-checks every rule before each send."""
    campaign = await _owned_campaign(session, idea.id, campaign_id)
    ids = await service.approved_ids(session, campaign.id, data.message_ids)
    if not ids:
        raise HTTPException(status.HTTP_409_CONFLICT, "No approved messages to send")
    try:
        await queue.enqueue_job(
            "send_campaign", str(campaign.id), [str(i) for i in ids] if data.message_ids else None
        )
    except Exception as exc:
        logger.exception("could not enqueue send_campaign")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _UNAVAILABLE) from exc
    return SendQueued(queued=len(ids))


# ---------- global: settings & suppressions ----------


@global_router.get("/outreach/settings", response_model=OutreachSettings)
async def outreach_settings(session: SessionDep) -> OutreachSettings:
    s = get_settings()
    provider = get_email_provider()
    return OutreachSettings(
        sending_enabled=provider.enabled,
        provider=f"{provider.name}://{s.smtp_host}:{s.smtp_port}" if provider.enabled else "none",
        sender_name=s.email_from_name,
        sender_address=s.email_from_address,
        sender_ready=bool(s.email_from_name.strip() and s.email_from_address.strip()),
        daily_limit=s.outreach_daily_limit,
        cooldown_days=s.outreach_cooldown_days,
        sent_today=await service.sent_today(session),
        postal_address=s.email_postal_address,
    )


@global_router.get("/suppressions", response_model=list[SuppressionRead])
async def list_suppressions(session: SessionDep) -> list:
    return await service.list_suppressions(session)


@global_router.post(
    "/suppressions", response_model=SuppressionRead, status_code=status.HTTP_201_CREATED
)
async def add_suppression(data: SuppressionCreate, session: SessionDep):
    if not safety.is_valid_email(data.email):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Not an email address")
    row = await service.add_suppression(
        session, data.email, SuppressionReason.MANUAL, note=data.note
    )
    await session.commit()
    return row


@global_router.delete("/suppressions/{suppression_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_suppression(suppression_id: uuid.UUID, session: SessionDep) -> None:
    try:
        await service.delete_suppression(session, suppression_id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except service.OutreachError as exc:
        raise _conflict(exc) from exc


# ---------- public: unsubscribe ----------


_PAGE_CSS = """
body { font: 16px/1.5 Georgia, serif; background: #f6f1e7; color: #1d1a16;
       margin: 0; padding: 48px 16px; }
main { max-width: 30rem; margin: auto; }
h1 { font-weight: normal; font-size: 1.8rem; }
button { font: inherit; padding: .5rem 1.2rem; border: 1px solid currentColor;
         background: #1d1a16; color: #f6f1e7; cursor: pointer; }
@media (prefers-color-scheme: dark) {
  body { background: #16140f; color: #ece5d8; }
  button { background: #ece5d8; color: #16140f; }
}
"""


def _page(title: str, body: str, code: int = 200) -> HTMLResponse:
    t = html.escape(title)
    doc = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<meta name="robots" content="noindex"><title>{t}</title><style>{_PAGE_CSS}</style>'
        f"</head><body><main><h1>{t}</h1>{body}</main></body></html>"
    )
    return HTMLResponse(doc, status_code=code)


@public_router.get("/unsubscribe/{token}", response_class=HTMLResponse)
async def unsubscribe_page(token: str) -> HTMLResponse:
    """Confirmation page. GET never unsubscribes, so link scanners can't trigger it."""
    s = get_settings()
    if safety.parse_unsubscribe_token(s.outreach_secret, token) is None:
        return _page("Link not recognised", "<p>This unsubscribe link isn't valid.</p>", 404)
    sender = html.escape(s.email_from_name or "the sender")
    return _page(
        "Stop these emails?",
        f"<p>{sender} won't email this address again.</p>"
        '<form method="post"><button type="submit">Unsubscribe</button></form>',
    )


@public_router.post("/unsubscribe/{token}", response_class=HTMLResponse)
async def unsubscribe(token: str, session: SessionDep) -> HTMLResponse:
    """Form submit and RFC 8058 one-click (`List-Unsubscribe=One-Click`)."""
    if not await service.unsubscribe(session, token, get_settings().outreach_secret):
        return _page("Link not recognised", "<p>This unsubscribe link isn't valid.</p>", 404)
    return _page("You're unsubscribed", "<p>You won't receive any more emails from me.</p>")
