import re
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.email.base import EmailRecipientRefusedError, EmailTransientError
from app.email.fake import FakeEmailProvider
from app.llm.fake import FakeProvider
from app.llm.router import LLMRouter
from app.llm.tasks import ProviderName
from app.modules.ideas.models import Idea
from app.modules.outreach import safety
from app.modules.outreach import service as outreach
from app.modules.outreach.models import (
    REDACTED,
    Message,
    MessageStatus,
    OutreachCampaign,
    Suppression,
    SuppressionReason,
)
from app.modules.outreach.schemas import CampaignCreate, MessageUpdate
from app.modules.prospects import service as prospects
from app.modules.prospects.models import Contact
from tests.test_prospects import idea, import_company  # noqa: F401  (fixture)

SETTINGS = Settings(
    _env_file=None,
    smtp_host="smtp.test",
    email_from_name="Ada Founder",
    email_from_address="ada@founder.test",
    outreach_secret="test-secret",
    public_api_url="http://api.test",
    outreach_daily_limit=20,
    outreach_cooldown_days=30,
)
NOW = datetime(2026, 11, 3, 15, 0, tzinfo=UTC)
PURPOSE = "I'm researching how contractors produce weekly owner reports."


def draft_output(**overrides) -> dict:
    out = {
        "subject": "Quick question about weekly reports",
        "body": "Hi Jane,\n\nI saw your team prepares weekly progress reports for owners. "
        "How long does that take each week?\n\nAda",
        "cited_refs": ["E1"],
        "why_selected": [
            {"statement": "Project engineer at a GC", "kind": "fact", "evidence_ids": ["E1"]}
        ],
    }
    return out | overrides


def llm_with(*responses) -> tuple[LLMRouter, FakeProvider]:
    fake = FakeProvider("local", list(responses))

    async def no_sleep(_: float) -> None:
        return None

    return LLMRouter({ProviderName.LOCAL: fake}, allow_downgrade=False, sleep=no_sleep), fake


async def setup_campaign(session: AsyncSession, idea: Idea, **kw) -> OutreachCampaign:  # noqa: F811
    await import_company(session, idea)
    data = {"name": "Owner reports", "purpose": PURPOSE} | kw
    return await outreach.create_campaign(session, idea, CampaignCreate(**data))


async def contact_id(session: AsyncSession) -> uuid.UUID:
    return await session.scalar(select(Contact.id).where(Contact.name == "Jane Roe"))


async def ready_message(
    session: AsyncSession,
    campaign: OutreachCampaign,
    *,
    email: str = "jane@abc.test",
    approve: bool = True,
) -> Message:
    """A drafted (and by default approved) message to Jane."""
    [message], _ = await outreach.create_drafts(session, campaign, [await contact_id(session)])
    llm, _ = llm_with(draft_output())
    await outreach.generate_draft(session, llm, message.id, SETTINGS)
    await session.refresh(message)
    await outreach.update_message(session, message, MessageUpdate(to_email=email))
    if approve:
        await outreach.approve(session, message)
    return message


async def send(session: AsyncSession, campaign, provider=None, now=NOW, **kw) -> dict:
    return await outreach.send_campaign(
        session, provider or FakeEmailProvider(), campaign.id, SETTINGS, now=now, **kw
    )


# ---------- pure helpers ----------


def test_unsubscribe_token_roundtrip_and_tamper() -> None:
    mid = uuid.uuid4()
    token = safety.unsubscribe_token("s", mid)
    assert safety.parse_unsubscribe_token("s", token) == mid
    assert safety.parse_unsubscribe_token("other", token) is None
    assert safety.parse_unsubscribe_token("s", token[:-2] + "xx") is None
    assert safety.parse_unsubscribe_token("s", "garbage") is None
    other = safety.unsubscribe_token("s", uuid.uuid4())
    assert (
        safety.parse_unsubscribe_token("s", token.split(".")[0] + "." + other.split(".")[1]) is None
    )


def test_approval_hash_tracks_content() -> None:
    h = safety.approval_hash("A@x.test", "s", "b")
    assert h == safety.approval_hash("a@x.test ", "s", "b")
    assert h != safety.approval_hash("a@x.test", "s", "b!")
    assert h != safety.approval_hash("b@x.test", "s", "b")


def test_draft_checks_flag_pitch_and_hype() -> None:
    checks = safety.draft_checks(
        "Book a demo", "Hello! Our platform is revolutionary. Want it? Really?", "Jane Roe"
    )
    text = " ".join(checks)
    assert "sales pitch" in text and "Exaggerated" in text
    assert "more than one question" in text and "Jane" in text
    assert safety.draft_checks("Q", "Hi Jane, how long does it take?", "Jane Roe") == []


def test_footer_has_identity_and_opt_out() -> None:
    f = safety.footer(
        sender_name="Ada", purpose=PURPOSE, unsubscribe_url="http://u", postal_address="1 St"
    )
    assert "Ada. I'm researching" in f and 'reply "stop"' in f and "http://u" in f and "1 St" in f


# ---------- drafting ----------


async def test_draft_maps_and_verifies_citations(session: AsyncSession, idea: Idea) -> None:  # noqa: F811
    campaign = await setup_campaign(session, idea)
    [message], _ = await outreach.create_drafts(session, campaign, [await contact_id(session)])
    assert message.status == MessageStatus.DRAFTING and message.to_email is None
    llm, fake = llm_with(draft_output())
    assert await outreach.generate_draft(session, llm, message.id, SETTINGS) == MessageStatus.DRAFT
    await session.refresh(message)

    prompt = fake.calls[0].prompt
    assert "Jane Roe, Project Engineer at ABC Builders" in prompt
    assert "Sender: Ada Founder" in prompt and PURPOSE in prompt
    e1_quote = re.search(r'E1: "([^"]+)"', prompt).group(1)
    company = await prospects.get_company(session, idea.id, message.company_id)
    company_ev = {str(e) for e in await prospects.company_evidence_ids(session, company.id)}
    assert message.cited_evidence_ids and set(message.cited_evidence_ids) <= company_ev
    [cited] = (await outreach.message_detail(session, message))["cited_evidence"]
    assert cited["quote"] == e1_quote
    assert message.why_selected[0]["evidence_ids"] == message.cited_evidence_ids
    assert message.checks == []


async def test_hallucinated_citation_leaves_empty_draft(session: AsyncSession, idea: Idea) -> None:  # noqa: F811
    campaign = await setup_campaign(session, idea)
    [message], _ = await outreach.create_drafts(session, campaign, [await contact_id(session)])
    bad = draft_output(cited_refs=["E9"])
    llm, fake = llm_with(bad, bad)
    await outreach.generate_draft(session, llm, message.id, SETTINGS)
    await session.refresh(message)
    assert len(fake.calls) == 2  # retried once
    assert message.status == MessageStatus.DRAFT
    assert message.body == "" and message.subject == ""  # no filler text
    assert "Couldn't generate a draft" in message.draft_error


async def test_duplicate_and_suppressed_contacts_skipped(session: AsyncSession, idea: Idea) -> None:  # noqa: F811
    campaign = await setup_campaign(session, idea)
    cid = await contact_id(session)
    created, _ = await outreach.create_drafts(session, campaign, [cid, cid])
    assert len(created) == 1
    created, skipped = await outreach.create_drafts(session, campaign, [cid, uuid.uuid4()])
    assert created == [] and {s["reason"] for s in skipped} == {
        "Already in this campaign",
        "Contact not found on this idea",
    }


# ---------- the approval gate ----------


async def test_unapproved_message_is_never_sent(session: AsyncSession, idea: Idea) -> None:  # noqa: F811
    campaign = await setup_campaign(session, idea)
    message = await ready_message(session, campaign, approve=False)
    provider = FakeEmailProvider()
    report = await send(session, campaign, provider, message_ids=[message.id])
    assert provider.sent == [] and report["sent"] == 0
    await session.refresh(message)
    assert message.status == MessageStatus.DRAFT and message.sent_at is None


async def test_approval_requires_address_and_content(session: AsyncSession, idea: Idea) -> None:  # noqa: F811
    campaign = await setup_campaign(session, idea)
    [message], _ = await outreach.create_drafts(session, campaign, [await contact_id(session)])
    with pytest.raises(outreach.OutreachError):  # still drafting
        await outreach.approve(session, message)
    llm, _ = llm_with(draft_output())
    await outreach.generate_draft(session, llm, message.id, SETTINGS)
    await session.refresh(message)
    with pytest.raises(outreach.OutreachError, match="email address"):
        await outreach.approve(session, message)
    with pytest.raises(outreach.OutreachError, match="email address"):
        await outreach.update_message(session, message, MessageUpdate(to_email="not-an-email"))
    await outreach.update_message(session, message, MessageUpdate(to_email="Jane@ABC.test"))
    assert message.to_email == "jane@abc.test" and message.to_email_source == "user_entered"
    await outreach.approve(session, message)
    assert message.status == MessageStatus.APPROVED and message.approved_hash


async def test_edit_after_approval_requires_reapproval(session: AsyncSession, idea: Idea) -> None:  # noqa: F811
    campaign = await setup_campaign(session, idea)
    message = await ready_message(session, campaign)
    await outreach.update_message(session, message, MessageUpdate(body="Hi Jane, one question?"))
    assert message.status == MessageStatus.DRAFT and message.approved_hash is None
    provider = FakeEmailProvider()
    await send(session, campaign, provider)
    assert provider.sent == []


async def test_content_changed_behind_the_gate_is_not_sent(
    session: AsyncSession,
    idea: Idea,  # noqa: F811
) -> None:
    campaign = await setup_campaign(session, idea)
    message = await ready_message(session, campaign)
    message.body = "Something nobody approved"  # bypassing update_message
    await session.commit()
    provider = FakeEmailProvider()
    report = await send(session, campaign, provider)
    assert provider.sent == [] and report["failed"] == 1
    await session.refresh(message)
    assert message.status == MessageStatus.DRAFT
    assert "approve it again" in message.send_error


async def test_reject_and_reopen(session: AsyncSession, idea: Idea) -> None:  # noqa: F811
    campaign = await setup_campaign(session, idea)
    message = await ready_message(session, campaign)
    await outreach.reject(session, message)
    assert message.status == MessageStatus.REJECTED and message.approved_hash is None
    provider = FakeEmailProvider()
    await send(session, campaign, provider)
    assert provider.sent == []
    await outreach.reopen(session, message)
    assert message.status == MessageStatus.DRAFT


# ---------- sending & stored content ----------


async def test_sent_message_stores_exact_content(session: AsyncSession, idea: Idea) -> None:  # noqa: F811
    campaign = await setup_campaign(session, idea)
    message = await ready_message(session, campaign)
    provider = FakeEmailProvider()
    report = await send(session, campaign, provider)
    assert report["sent"] == 1
    [email] = provider.sent
    await session.refresh(message)
    assert message.status == MessageStatus.SENT and message.sent_at == NOW
    assert message.sent_body == email.body
    assert email.body.startswith(message.body)
    unsub = outreach.unsubscribe_url(SETTINGS, message.id)
    assert unsub in email.body and "Ada Founder. I'm researching" in email.body
    assert message.sent_headers["List-Unsubscribe"] == f"<{unsub}>"
    assert message.sent_headers["From"] == "Ada Founder <ada@founder.test>"
    assert message.sent_headers["To"] == "Jane Roe <jane@abc.test>"
    assert message.content_hash == safety.content_hash(message.sent_headers, message.sent_body)
    assert message.provider_message_id == f"<{message.id}@founder.test>"
    assert message.cited_evidence_ids  # the evidence behind it is kept

    # Sending again never resends.
    again = await send(session, campaign, provider)
    assert again["sent"] == 0 and len(provider.sent) == 1


async def test_sending_disabled_or_no_identity_defers(session: AsyncSession, idea: Idea) -> None:  # noqa: F811
    campaign = await setup_campaign(session, idea)
    await ready_message(session, campaign)
    report = await send(session, campaign, FakeEmailProvider(enabled=False))
    assert report["deferred"] == 1 and "disabled" in report["notes"][0]
    anon = SETTINGS.model_copy(update={"email_from_name": ""})
    report = await outreach.send_campaign(session, FakeEmailProvider(), campaign.id, anon, now=NOW)
    assert report["deferred"] == 1 and "real sender identity" in report["notes"][0]


async def test_paused_campaign_defers(session: AsyncSession, idea: Idea) -> None:  # noqa: F811
    campaign = await setup_campaign(session, idea)
    await ready_message(session, campaign)
    campaign.status = "paused"
    await session.commit()
    provider = FakeEmailProvider()
    report = await send(session, campaign, provider)
    assert provider.sent == [] and report["notes"] == ["Campaign is paused."]


async def test_transient_error_keeps_it_approved(session: AsyncSession, idea: Idea) -> None:  # noqa: F811
    campaign = await setup_campaign(session, idea)
    message = await ready_message(session, campaign)
    provider = FakeEmailProvider()
    provider.fail_with["jane@abc.test"] = EmailTransientError("timeout")
    report = await send(session, campaign, provider)
    await session.refresh(message)
    assert report["failed"] == 1 and message.status == MessageStatus.APPROVED
    assert message.send_error == "timeout"


async def test_refused_recipient_is_bounced_and_suppressed(
    session: AsyncSession,
    idea: Idea,  # noqa: F811
) -> None:
    campaign = await setup_campaign(session, idea)
    message = await ready_message(session, campaign)
    provider = FakeEmailProvider()
    provider.fail_with["jane@abc.test"] = EmailRecipientRefusedError("550")
    report = await send(session, campaign, provider)
    await session.refresh(message)
    assert report["bounced"] == 1 and message.status == MessageStatus.BOUNCED
    sup = await outreach.get_suppression(session, "jane@abc.test")
    assert sup.reason == SuppressionReason.BOUNCED


async def test_manual_bounce_suppresses(session: AsyncSession, idea: Idea) -> None:  # noqa: F811
    campaign = await setup_campaign(session, idea)
    message = await ready_message(session, campaign)
    await send(session, campaign)
    await outreach.mark_bounced(session, message)
    assert message.status == MessageStatus.BOUNCED
    assert await outreach.is_suppressed(session, "JANE@abc.test")


# ---------- suppression & limits ----------


async def test_suppressed_address_is_blocked_at_send(session: AsyncSession, idea: Idea) -> None:  # noqa: F811
    campaign = await setup_campaign(session, idea)
    message = await ready_message(session, campaign)
    await outreach.add_suppression(session, "Jane@abc.test", SuppressionReason.MANUAL)
    await session.commit()
    provider = FakeEmailProvider()
    report = await send(session, campaign, provider)
    await session.refresh(message)
    assert provider.sent == [] and report["blocked"] == 1
    assert message.status == MessageStatus.BLOCKED
    # …and approving another message to it is refused up front.
    with pytest.raises(outreach.OutreachError, match="suppression"):
        other = await outreach.create_campaign(
            session, idea, CampaignCreate(name="Two", purpose=PURPOSE)
        )
        await ready_message(session, other)


async def test_campaign_daily_limit(session: AsyncSession, idea: Idea) -> None:  # noqa: F811
    campaign = await setup_campaign(session, idea, daily_limit=1)
    await ready_message(session, campaign)
    # A second recipient at the same company.
    company_id = await session.scalar(select(Contact.company_id))
    sam = Contact(
        company_id=company_id,
        name="Sam Poe",
        name_key="sam poe",
        role="CFO",
        evidence_id=(await session.scalar(select(Contact))).evidence_id,
        source_url="https://abcbuilders.com/about",
        collected_at=NOW,
    )
    session.add(sam)
    await session.commit()
    [m2], _ = await outreach.create_drafts(session, campaign, [sam.id])
    llm, _ = llm_with(draft_output(body="Hi Sam, how long do reports take?"))
    await outreach.generate_draft(session, llm, m2.id, SETTINGS)
    await session.refresh(m2)
    await outreach.update_message(session, m2, MessageUpdate(to_email="sam@abc.test"))
    await outreach.approve(session, m2)

    provider = FakeEmailProvider()
    report = await send(session, campaign, provider)
    assert report["sent"] == 1 and report["deferred"] == 1
    assert "Campaign daily limit" in report["notes"][0]
    # Tomorrow the second one goes.
    report = await send(session, campaign, provider, now=NOW + timedelta(days=1))
    assert report["sent"] == 1 and len(provider.sent) == 2


async def test_global_daily_limit(session: AsyncSession, idea: Idea) -> None:  # noqa: F811
    campaign = await setup_campaign(session, idea)
    await ready_message(session, campaign)
    tight = SETTINGS.model_copy(update={"outreach_daily_limit": 0})
    provider = FakeEmailProvider()
    report = await outreach.send_campaign(session, provider, campaign.id, tight, now=NOW)
    assert provider.sent == [] and "Global daily limit" in report["notes"][0]


async def test_contact_frequency_limit_across_campaigns(
    session: AsyncSession,
    idea: Idea,  # noqa: F811
) -> None:
    first = await setup_campaign(session, idea)
    await ready_message(session, first)
    await send(session, first)
    second = await outreach.create_campaign(
        session, idea, CampaignCreate(name="Follow-up angle", purpose=PURPOSE)
    )
    message = await ready_message(session, second)
    provider = FakeEmailProvider()
    report = await send(session, second, provider, now=NOW + timedelta(days=5))
    await session.refresh(message)
    assert provider.sent == [] and report["blocked"] == 1
    assert "last 30 days" in message.blocked_reason
    # After the cooldown it would be allowed (re-approval needed after a block).
    assert message.status == MessageStatus.BLOCKED


# ---------- unsubscribe & deletion ----------


async def test_unsubscribe_end_to_end(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    idea: Idea,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.modules.outreach.router.get_settings", lambda: SETTINGS)
    async with session_maker() as session:
        campaign = await setup_campaign(session, idea)
        message = await ready_message(session, campaign)
        provider = FakeEmailProvider()
        await send(session, campaign, provider)
        url = re.search(r"http://api\.test(/unsubscribe/\S+)", provider.sent[0].body).group(1)

    page = await client.get(url)
    assert page.status_code == 200 and '<form method="post">' in page.text
    async with session_maker() as session:
        assert not await outreach.is_suppressed(session, "jane@abc.test")  # GET changes nothing

    done = await client.post(url)
    assert done.status_code == 200 and "unsubscribed" in done.text
    assert (await client.get("/unsubscribe/forged.token")).status_code == 404

    async with session_maker() as session:
        sup = await outreach.get_suppression(session, "jane@abc.test")
        assert sup.reason == SuppressionReason.UNSUBSCRIBED and sup.message_id == message.id
        # Nothing reaches that address again, from any campaign.
        other = await outreach.create_campaign(
            session, idea, CampaignCreate(name="Other", purpose=PURPOSE)
        )
        [m2], skipped = await outreach.create_drafts(session, other, [await contact_id(session)])
        llm, _ = llm_with(draft_output())
        await outreach.generate_draft(session, llm, m2.id, SETTINGS)
        await session.refresh(m2)
        await outreach.update_message(session, m2, MessageUpdate(to_email="jane@abc.test"))
        with pytest.raises(outreach.OutreachError, match="suppression"):
            await outreach.approve(session, m2)


async def test_delete_contact_suppresses_and_redacts(session: AsyncSession, idea: Idea) -> None:  # noqa: F811
    campaign = await setup_campaign(session, idea)
    sent = await ready_message(session, campaign)
    await send(session, campaign)
    await session.refresh(sent)
    kept_hash, sent_id = sent.content_hash, sent.id
    other = await outreach.create_campaign(
        session, idea, CampaignCreate(name="Other", purpose=PURPOSE)
    )
    draft = await ready_message(session, other, email="jane.roe@abc.test", approve=False)
    draft_id = draft.id

    assert await prospects.delete_contact(session, idea.id, await contact_id(session))
    session.expire_all()
    reasons = {s.email: s.reason for s in await session.scalars(select(Suppression))}
    assert reasons == {
        "jane@abc.test": SuppressionReason.DELETION_REQUEST,
        "jane.roe@abc.test": SuppressionReason.DELETION_REQUEST,
    }
    assert await session.get(Message, draft_id) is None  # unsent: deleted
    row = await session.get(Message, sent_id)
    assert row.status == MessageStatus.SENT and row.redacted_at is not None
    assert row.to_email is None and row.to_name == row.body == row.sent_body == REDACTED
    assert row.sent_headers is None and row.content_hash == kept_hash
    assert row.cited_evidence_ids and row.contact_id is None


# ---------- API ----------


async def test_outreach_api_flow(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    queue,
) -> None:
    created = await client.post(
        "/ideas", json={"title": "t", "description": "d", "target_market": "US"}
    )
    idea_id = created.json()["id"]
    async with session_maker() as session:
        idea_row = await session.get(Idea, uuid.UUID(idea_id))
        await import_company(session, idea_row)
        cid = await contact_id(session)

    r = await client.post(f"/ideas/{idea_id}/campaigns", json={"name": "C", "purpose": "short"})
    assert r.status_code == 422  # purpose too short
    r = await client.post(f"/ideas/{idea_id}/campaigns", json={"name": "C", "purpose": PURPOSE})
    assert r.status_code == 201
    camp = r.json()
    assert camp["stats"]["draft"] == 0 and camp["daily_limit"] == 10

    [rec] = (await client.get(f"/ideas/{idea_id}/outreach/recipients")).json()
    assert rec["name"] == "Jane Roe" and rec["campaign_ids"] == [] and not rec["suppressed"]

    r = await client.post(
        f"/ideas/{idea_id}/campaigns/{camp['id']}/drafts", json={"contact_ids": [str(cid)]}
    )
    assert r.status_code == 202
    [mid] = r.json()["created"]
    assert queue.jobs[-1] == ("draft_outreach", ([mid],))

    async with session_maker() as session:
        llm, _ = llm_with(draft_output())
        await outreach.generate_draft(session, llm, uuid.UUID(mid), SETTINGS)

    detail = (await client.get(f"/ideas/{idea_id}/messages/{mid}")).json()
    assert detail["status"] == "draft" and detail["prospect"]["name"] == "ABC Builders"
    assert detail["cited_evidence"][0]["url"].startswith("https://")
    assert detail["why_selected"][0]["kind"] == "fact"

    r = await client.post(f"/ideas/{idea_id}/campaigns/{camp['id']}/send", json={})
    assert r.status_code == 409  # nothing approved
    assert (await client.post(f"/ideas/{idea_id}/messages/{mid}/approve")).status_code == 409
    r = await client.patch(f"/ideas/{idea_id}/messages/{mid}", json={"to_email": "jane@abc.test"})
    assert r.json()["to_email_source"] == "user_entered"
    assert (await client.post(f"/ideas/{idea_id}/messages/{mid}/approve")).json()[
        "status"
    ] == "approved"

    r = await client.post(f"/ideas/{idea_id}/campaigns/{camp['id']}/send", json={})
    assert r.status_code == 202 and r.json() == {"queued": 1}
    assert queue.jobs[-1] == ("send_campaign", (camp["id"], None))

    msgs = (await client.get(f"/ideas/{idea_id}/campaigns/{camp['id']}/messages")).json()
    assert [m["status"] for m in msgs] == ["approved"]

    # Suppressions: manual entries can be removed, others can't.
    r = await client.post("/suppressions", json={"email": "Nope@x.test", "note": "asked by phone"})
    assert r.status_code == 201 and r.json()["email"] == "nope@x.test"
    assert (await client.post("/suppressions", json={"email": "bad"})).status_code == 422
    assert (await client.delete(f"/suppressions/{r.json()['id']}")).status_code == 204
    async with session_maker() as session:
        row = await outreach.add_suppression(session, "u@x.test", SuppressionReason.UNSUBSCRIBED)
        await session.commit()
    assert (await client.delete(f"/suppressions/{row.id}")).status_code == 409

    settings = (await client.get("/outreach/settings")).json()
    assert {"sending_enabled", "sender_ready", "daily_limit", "sent_today"} <= settings.keys()

    other_idea = (
        await client.post("/ideas", json={"title": "x", "description": "y", "target_market": "US"})
    ).json()
    assert (await client.get(f"/ideas/{other_idea['id']}/messages/{mid}")).status_code == 404


async def test_message_count_unchanged_by_failed_queue(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    queue,
) -> None:
    idea_id = (
        await client.post("/ideas", json={"title": "t", "description": "d", "target_market": "US"})
    ).json()["id"]
    async with session_maker() as session:
        await import_company(session, await session.get(Idea, uuid.UUID(idea_id)))
        cid = await contact_id(session)
    camp = (
        await client.post(f"/ideas/{idea_id}/campaigns", json={"name": "C", "purpose": PURPOSE})
    ).json()
    queue.fail = True
    r = await client.post(
        f"/ideas/{idea_id}/campaigns/{camp['id']}/drafts", json={"contact_ids": [str(cid)]}
    )
    assert r.status_code == 503
    async with session_maker() as session:
        [m] = list(await session.scalars(select(Message)))
        assert m.status == MessageStatus.DRAFT and "job queue" in m.draft_error
        assert await session.scalar(select(func.count()).select_from(Message)) == 1
