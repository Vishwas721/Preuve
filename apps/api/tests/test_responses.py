import uuid
from datetime import date
from email.message import EmailMessage

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.llm.fake import FakeProvider
from app.llm.router import LLMRouter
from app.llm.tasks import ProviderName
from app.modules.ideas.models import Idea
from app.modules.outreach import service as outreach
from app.modules.outreach.models import Message, MessageStatus, SuppressionReason
from app.modules.prospects import service as prospects
from app.modules.prospects.models import CompanyEvidence
from app.modules.research.models import Evidence, EvidenceOrigin, WebSource
from app.modules.responses import mailbox, text
from app.modules.responses import service as responses
from app.modules.responses.models import Response, ResponseChannel, ResponseStatus
from app.modules.responses.schemas import ResponsePaste
from app.modules.wtp import service as wtp
from app.modules.wtp.models import Commitment, WtpSignal, WtpSource
from tests.test_outreach import contact_id, ready_message, send, setup_campaign
from tests.test_prospects import idea  # noqa: F401  (fixture)

REPLY = (
    "Hi Ada,\n\nWe actually have this problem every week. Our PMs spend about 4-5 hours creating "
    "reports. We currently use Excel and photos from WhatsApp. Honestly it's painful and I'd "
    "happily pay for something that fixes it.\n\nDave\n\n"
    "On Tue, 3 Nov 2026 at 17:17, Ada Founder <ada@founder.test> wrote:\n> Hi Dave, ..."
)


def classification(**overrides) -> dict:
    out = {
        "sentiment": "positive",
        "problem_confirmed": {"value": "yes", "quote": "We actually have this problem every week"},
        "pain": {
            "value": "report creation",
            "quote": "Our PMs spend about 4-5 hours creating reports",
        },
        "frequency": {"value": "weekly", "quote": "every week"},
        "current_solution": {
            "value": "Excel + WhatsApp",
            "quote": "We currently use Excel and photos from WhatsApp",
        },
        "time_or_cost": {"value": "4-5 h/week", "quote": "spend about 4-5 hours creating reports"},
        "severity": {"value": "high", "quote": "Honestly it's painful"},
        "solution_satisfaction": {"value": "low", "quote": ""},
        "interest": {"value": "unclear", "quote": ""},
        "willingness_to_pay": {
            "value": "strong",
            "quote": "I'd happily pay for something that fixes it",
        },
    }
    return out | overrides


def llm_with(*responses_) -> tuple[LLMRouter, FakeProvider, FakeProvider]:
    local, gemini = FakeProvider("local", list(responses_)), FakeProvider("gemini")

    async def no_sleep(_: float) -> None:
        return None

    router = LLMRouter({ProviderName.LOCAL: local, ProviderName.GEMINI: gemini}, sleep=no_sleep)
    return router, local, gemini


async def sent_message(session: AsyncSession, idea: Idea) -> Message:
    campaign = await setup_campaign(session, idea)
    message = await ready_message(session, campaign)
    await send(session, campaign)
    await session.refresh(message)
    return message


def email(
    *,
    body: str = REPLY,
    sender: str = "Dave Roe <jane@abc.test>",
    in_reply_to: str | None = None,
    message_id: str = "<reply-1@abc.test>",
) -> bytes:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = "ada@founder.test"
    msg["Subject"] = "Re: Quick question about weekly reports"
    msg["Date"] = "Wed, 04 Nov 2026 09:00:00 +0000"
    msg["Message-ID"] = message_id
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    msg.set_content(body)
    return msg.as_bytes()


def dsn(original_id: str, recipient: str = "jane@abc.test") -> bytes:
    return (
        "From: Mail Delivery Subsystem <mailer-daemon@googlemail.com>\r\n"
        "To: ada@founder.test\r\nSubject: Delivery Status Notification (Failure)\r\n"
        "Message-ID: <dsn-1@google.com>\r\nMIME-Version: 1.0\r\n"
        'Content-Type: multipart/report; report-type=delivery-status; boundary="b"\r\n\r\n'
        "--b\r\nContent-Type: text/plain\r\n\r\nAddress not found.\r\n"
        "--b\r\nContent-Type: message/delivery-status\r\n\r\nReporting-MTA: dns; google.com\r\n\r\n"
        f"Final-Recipient: rfc822; {recipient}\r\nAction: failed\r\nStatus: 5.1.1\r\n"
        "--b\r\nContent-Type: text/rfc822-headers\r\n\r\n"
        f"Message-ID: {original_id}\r\nSubject: Quick question\r\n--b--\r\n"
    ).encode()


class FakeMailbox(mailbox.Mailbox):
    def __init__(self, raws: list[bytes]) -> None:
        self.raws = raws
        self.since: date | None = None

    async def fetch_since(self, since: date) -> list[bytes]:
        self.since = since
        return self.raws


# ---------- pure helpers ----------


def test_strip_quoted_history() -> None:
    assert text.strip_quoted(REPLY).endswith("Dave")
    assert "wrote:" not in text.strip_quoted(REPLY)
    outlook = "Sure, call me.\n\n-----Original Message-----\nFrom: Ada\nHi"
    assert text.strip_quoted(outlook) == "Sure, call me."
    assert text.strip_quoted("> quoted only\nnew line") == "new line"


def test_recommended_action_is_deterministic() -> None:
    from app.modules.responses.prompts import ResponseClassification

    c = ResponseClassification.model_validate(classification())
    assert text.recommended_action(c, opt_out=False)[0] == "interview"
    assert text.recommended_action(c, opt_out=True)[0] == "none"
    no = ResponseClassification.model_validate(
        classification(problem_confirmed={"value": "no", "quote": "x"})
    )
    assert text.recommended_action(no, opt_out=False)[0] == "close"


def test_referenced_ids_and_bounce_report() -> None:
    mid = uuid.uuid4()
    assert text.referenced_ids(f"<{mid}@founder.test> <other@x>") == [mid]
    raw = dsn(f"<{mid}@founder.test>")
    report = text.bounce_report(text.parse(raw), raw)
    assert report.message_ids == [mid] and report.recipient == "jane@abc.test"
    plain = email()
    assert text.bounce_report(text.parse(plain), plain) is None


# ---------- paste + analysis ----------


async def test_pasted_reply_becomes_fact_evidence(session: AsyncSession, idea: Idea) -> None:
    message = await sent_message(session, idea)
    r = await responses.create_paste(
        session, idea, ResponsePaste(text=REPLY, message_id=message.id)
    )
    assert r.status == ResponseStatus.QUEUED and "wrote:" not in r.raw_text
    assert r.from_email == "jane@abc.test" and r.contact_id == message.contact_id

    llm, local, gemini = llm_with(classification())
    assert await responses.analyze_response(session, llm, r.id) == ResponseStatus.DONE
    assert local.calls and not gemini.calls
    assert REPLY.split("\n")[2][:40] in local.calls[0].prompt

    await session.refresh(r)
    ev = list(await session.scalars(select(Evidence).where(Evidence.response_id == r.id)))
    assert ev and all(e.origin == EvidenceOrigin.REPLY and e.kind == "fact" for e in ev)
    assert all(e.quote in r.raw_text for e in ev)
    assert all(e.verification == "verified" for e in ev)
    by_label = {e.statement.split(": ", 1)[1]: e for e in ev}
    assert by_label["problem confirmed: yes"].stance == "supports"
    assert by_label["current solution: Excel + WhatsApp"].stance == "neutral"
    src = await session.get(WebSource, ev[0].source_id)
    assert src.url == f"preuve://responses/{r.id}" and src.text == r.raw_text
    # Linked to the company, so it feeds the lead score.
    linked = set(
        await session.scalars(
            select(CompanyEvidence.evidence_id).where(CompanyEvidence.company_id == r.company_id)
        )
    )
    assert {e.id for e in ev} <= linked
    assert r.classification["recommended_action"]["value"] == "interview"

    # The AI proposes a *stated* willingness, never a commitment.
    [signal] = await wtp.list_signals(session, idea.id)
    assert signal.stated_willingness == "strong" and signal.commitment == Commitment.NONE
    assert signal.source == WtpSource.AI and signal.stated_evidence_id in {e.id for e in ev}


async def test_unverifiable_quotes_are_dropped(session: AsyncSession, idea: Idea) -> None:
    message = await sent_message(session, idea)
    r = await responses.create_paste(
        session, idea, ResponsePaste(text=REPLY, message_id=message.id)
    )
    made_up = classification(
        frequency={"value": "daily", "quote": "we do this every single day"},
        willingness_to_pay={"value": "strong", "quote": "take my money"},
    )
    llm, _, _ = llm_with(made_up)
    await responses.analyze_response(session, llm, r.id)
    await session.refresh(r)
    assert {d["quote"] for d in r.dropped} == {"we do this every single day", "take my money"}
    assert r.classification["frequency"]["quote"] == ""  # never shown as their words
    quotes = set(await session.scalars(select(Evidence.quote).where(Evidence.response_id == r.id)))
    assert "take my money" not in quotes
    assert await wtp.list_signals(session, idea.id) == []


async def test_llm_failure_marks_reply_failed(session: AsyncSession, idea: Idea) -> None:
    r = await responses.create_paste(session, idea, ResponsePaste(text="Sounds interesting."))
    llm, _, gemini = llm_with("not json", "still not json")
    assert await responses.analyze_response(session, llm, r.id) == ResponseStatus.FAILED
    assert not gemini.calls  # private: no escalation to Gemini
    await session.refresh(r)
    assert "Couldn't classify" in r.error
    assert (
        await session.scalar(
            select(func.count()).select_from(Evidence).where(Evidence.response_id == r.id)
        )
        == 0
    )


async def test_reanalysis_replaces_evidence(session: AsyncSession, idea: Idea) -> None:
    message = await sent_message(session, idea)
    r = await responses.create_paste(
        session, idea, ResponsePaste(text=REPLY, message_id=message.id)
    )
    llm, _, _ = llm_with(classification(), classification(pain={"value": "", "quote": ""}))
    await responses.analyze_response(session, llm, r.id)
    first = await session.scalar(
        select(func.count()).select_from(Evidence).where(Evidence.response_id == r.id)
    )
    await responses.reanalyze(session, r)
    await responses.analyze_response(session, llm, r.id)
    second = await session.scalar(
        select(func.count()).select_from(Evidence).where(Evidence.response_id == r.id)
    )
    assert second == first - 1
    assert (
        await session.scalar(
            select(func.count())
            .select_from(WebSource)
            .where(WebSource.url == f"preuve://responses/{r.id}")
        )
        == 1
    )


async def test_opt_out_reply_suppresses_sender(session: AsyncSession, idea: Idea) -> None:
    message = await sent_message(session, idea)
    r = await responses.create_paste(
        session, idea, ResponsePaste(text="Please stop emailing me.", message_id=message.id)
    )
    assert r.opt_out
    sup = await outreach.get_suppression(session, "jane@abc.test")
    assert sup.reason == SuppressionReason.UNSUBSCRIBED
    llm, _, _ = llm_with(
        classification(sentiment="negative", interest={"value": "low", "quote": ""})
    )
    await responses.analyze_response(session, llm, r.id)
    await session.refresh(r)
    assert r.classification["recommended_action"]["value"] == "none"


# ---------- IMAP ----------


async def test_imap_reply_matched_by_header(session: AsyncSession, idea: Idea) -> None:
    message = await sent_message(session, idea)
    box = FakeMailbox(
        [
            email(in_reply_to=message.provider_message_id, sender="Someone Else <other@x.test>"),
            email(message_id="<unrelated@x.test>", sender="News <news@x.test>"),
        ]
    )
    report = await mailbox.poll(session, box)
    assert report["reply"] == 1 and report["unmatched"] == 1
    assert box.since <= message.sent_at.date()
    [r] = await responses.list_responses(session, idea.id)
    assert r.message_id == message.id and r.contact_id == message.contact_id
    assert r.channel == ResponseChannel.IMAP and r.rfc_message_id == "<reply-1@abc.test>"
    assert "wrote:" not in r.raw_text
    # Unmatched mail is never stored.
    assert await session.scalar(select(func.count()).select_from(Response)) == 1
    # A second poll doesn't duplicate.
    again = await mailbox.poll(session, box)
    assert again["duplicate"] == 1 and again["reply"] == 0


async def test_imap_reply_matched_by_sender(session: AsyncSession, idea: Idea) -> None:
    message = await sent_message(session, idea)
    report = await mailbox.poll(session, FakeMailbox([email(sender="Jane <JANE@abc.test>")]))
    assert report["reply"] == 1
    [r] = await responses.list_responses(session, idea.id)
    assert r.message_id == message.id


async def test_imap_bounce_report_marks_bounced(session: AsyncSession, idea: Idea) -> None:
    message = await sent_message(session, idea)
    report = await mailbox.poll(session, FakeMailbox([dsn(message.provider_message_id)]))
    assert report["bounce"] == 1 and report["reply"] == 0
    await session.refresh(message)
    assert message.status == MessageStatus.BOUNCED
    assert (await outreach.get_suppression(session, "jane@abc.test")).reason == "bounced"
    assert await responses.list_responses(session, idea.id) == []


async def test_imap_opt_out_suppresses(session: AsyncSession, idea: Idea) -> None:
    message = await sent_message(session, idea)
    await mailbox.poll(
        session, FakeMailbox([email(body="STOP", in_reply_to=message.provider_message_id)])
    )
    [r] = await responses.list_responses(session, idea.id)
    assert r.opt_out and await outreach.is_suppressed(session, "jane@abc.test")


async def test_poll_before_any_send_does_nothing(session: AsyncSession) -> None:
    box = FakeMailbox([email()])
    report = await mailbox.poll(session, box)
    assert report["error"] == "Nothing sent yet." and box.since is None


# ---------- deletion ----------


async def test_delete_contact_removes_replies_and_evidence(
    session: AsyncSession, idea: Idea
) -> None:
    message = await sent_message(session, idea)
    r = await responses.create_paste(
        session, idea, ResponsePaste(text=REPLY, message_id=message.id)
    )
    llm, _, _ = llm_with(classification())
    await responses.analyze_response(session, llm, r.id)
    user_row = WtpSignal(
        idea_id=idea.id, contact_id=message.contact_id, customer_label="Jane", source=WtpSource.USER
    )
    session.add(user_row)
    await session.commit()
    rid = r.id

    assert await prospects.delete_contact(session, idea.id, await contact_id(session))
    session.expire_all()
    assert await session.get(Response, rid) is None
    assert (
        await session.scalar(
            select(func.count()).select_from(Evidence).where(Evidence.origin == "reply")
        )
        == 0
    )
    assert (
        await session.scalar(
            select(func.count()).select_from(WebSource).where(WebSource.url.like("preuve://%"))
        )
        == 0
    )
    assert await session.scalar(select(func.count()).select_from(WtpSignal)) == 0


async def test_delete_reply_keeps_user_wtp(session: AsyncSession, idea: Idea) -> None:
    message = await sent_message(session, idea)
    r = await responses.create_paste(
        session, idea, ResponsePaste(text=REPLY, message_id=message.id)
    )
    llm, _, _ = llm_with(classification())
    await responses.analyze_response(session, llm, r.id)
    [proposal] = await wtp.list_signals(session, idea.id)
    from app.modules.wtp.schemas import WtpUpdate

    await wtp.update(session, proposal, WtpUpdate(commitment=Commitment.PILOT))
    assert proposal.source == WtpSource.USER and proposal.committed_at is not None
    await responses.delete_response(session, r)
    [kept] = await wtp.list_signals(session, idea.id)
    assert kept.commitment == Commitment.PILOT


# ---------- API ----------


async def api_idea(client: AsyncClient, session_maker) -> Idea:
    created = await client.post(
        "/ideas", json={"title": "t", "description": "d", "target_market": "US"}
    )
    async with session_maker() as session:
        return await session.get(Idea, uuid.UUID(created.json()["id"]))


async def test_responses_api(
    client: AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    queue,
) -> None:
    idea = await api_idea(client, session_maker)
    async with session_maker() as session:
        message = await sent_message(session, await session.get(Idea, idea.id))
    base = f"/ideas/{idea.id}"
    r = await client.post(f"{base}/responses", json={"text": REPLY, "message_id": str(message.id)})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    assert queue.jobs[-1] == ("analyze_response", (rid,))
    assert r.json()["original"]["subject"] == message.subject

    async with session_maker() as session:
        llm, _, _ = llm_with(classification())
        await responses.analyze_response(session, llm, uuid.UUID(rid))

    detail = (await client.get(f"{base}/responses/{rid}")).json()
    assert detail["status"] == "done" and len(detail["evidence_ids"]) >= 5
    research = (await client.get(f"{base}/research")).json()
    first_party = [e for e in research["evidence"] if e["origin"] == "reply"]
    assert first_party and first_party[0]["url"].startswith("preuve://responses/")
    assert first_party[0]["import_id"] is None

    dash = (await client.get(f"{base}/responses/dashboard")).json()
    assert dash["sent"] == 1 and dash["replies"] == 1 and dash["reply_rate"] == 1.0
    assert dash["positive"] == 1 and dash["problem_confirmed"] == 1
    assert dash["interview_recommended"] == 1 and dash["stated_strong"] == 1
    assert dash["top_pains"][0]["quote"].startswith("Our PMs spend")
    assert dash["frequencies"] == [{"value": "weekly", "count": 1}]

    bad = await client.post(
        f"{base}/responses", json={"text": "x", "message_id": str(uuid.uuid4())}
    )
    assert bad.status_code == 422

    assert (await client.delete(f"{base}/responses/{rid}")).status_code == 204
    assert (await client.get(f"{base}/responses/{rid}")).status_code == 404

    inbox = (await client.get("/outreach/inbox")).json()
    assert set(inbox) == {"enabled", "mailbox", "last_poll"}


async def test_paste_with_queue_down(
    client: AsyncClient, session_maker: async_sessionmaker[AsyncSession], queue
) -> None:
    idea = await api_idea(client, session_maker)
    queue.fail = True
    r = await client.post(f"/ideas/{idea.id}/responses", json={"text": "Sure, happy to chat."})
    assert r.status_code == 503
    async with session_maker() as session:
        [row] = list(await session.scalars(select(Response)))
        assert row.status == ResponseStatus.FAILED and "job queue" in row.error


async def test_verbatim_values_recover_missing_quotes(session: AsyncSession, idea: Idea) -> None:
    """What qwen2.5 actually returned live: the customer's words in `value`, quotes empty."""
    message = await sent_message(session, idea)
    reply = (
        "We actually have this problem every week. Our PMs spend about 4-5 hours creating "
        "reports. We currently use Excel and photos from WhatsApp, and honestly nobody likes it."
    )
    r = await responses.create_paste(
        session, idea, ResponsePaste(text=reply, message_id=message.id)
    )
    live = {
        "sentiment": "positive",
        "problem_confirmed": {"value": "yes", "quote": ""},
        "pain": {"value": "nobody likes it", "quote": ""},
        "frequency": {"value": "every week", "quote": ""},
        "current_solution": {"value": "Excel and photos from WhatsApp", "quote": ""},
        "time_or_cost": {"value": "4-5 hours a week", "quote": ""},  # not verbatim
        "severity": {"value": "high", "quote": ""},
        "solution_satisfaction": {"value": "low", "quote": ""},
        "interest": {"value": "medium", "quote": ""},
        "willingness_to_pay": {"value": "strong", "quote": ""},
    }
    llm, _, _ = llm_with(live)
    await responses.analyze_response(session, llm, r.id)
    await session.refresh(r)
    quotes = set(await session.scalars(select(Evidence.quote).where(Evidence.response_id == r.id)))
    assert quotes == {"nobody likes it", "every week", "Excel and photos from WhatsApp"}
    assert r.classification["frequency"]["quote"] == "every week"
    assert r.classification["time_or_cost"]["quote"] == ""  # paraphrase: never shown as theirs
    assert await wtp.list_signals(session, idea.id) == []  # no quote, no proposal
