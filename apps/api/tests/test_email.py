import smtplib

import pytest

from app.email.base import (
    EmailDisabledError,
    EmailRecipientRefusedError,
    EmailTransientError,
    OutgoingEmail,
)
from app.email.smtp import SmtpProvider, build_message

EMAIL = OutgoingEmail(
    from_name="Ada Founder",
    from_address="ada@example.com",
    to_name="Grace Ops",
    to_address="grace@acme.test",
    subject="A quick research question",
    body="Hi Grace,\n\nOne question.\n",
    message_id="<abc@example.com>",
    headers={"List-Unsubscribe": "<https://x/unsubscribe/t>"},
)


class _FakeSMTP:
    instances: list["_FakeSMTP"] = []
    raise_on_send: Exception | None = None

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host, self.port = host, port
        self.calls: list[str] = []
        self.sent = []
        _FakeSMTP.instances.append(self)

    def __enter__(self) -> "_FakeSMTP":
        return self

    def __exit__(self, *a: object) -> None:
        pass

    def starttls(self) -> None:
        self.calls.append("starttls")

    def login(self, user: str, pw: str) -> None:
        self.calls.append(f"login:{user}")

    def send_message(self, msg: object) -> None:
        if _FakeSMTP.raise_on_send:
            raise _FakeSMTP.raise_on_send
        self.sent.append(msg)


@pytest.fixture
def fake_smtp(monkeypatch: pytest.MonkeyPatch) -> type[_FakeSMTP]:
    _FakeSMTP.instances = []
    _FakeSMTP.raise_on_send = None
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    return _FakeSMTP


def test_build_message_headers() -> None:
    msg = build_message(EMAIL)
    assert msg["From"] == "Ada Founder <ada@example.com>"
    assert msg["To"] == "Grace Ops <grace@acme.test>"
    assert msg["Message-ID"] == "<abc@example.com>"
    assert msg["List-Unsubscribe"] == "<https://x/unsubscribe/t>"
    assert msg.get_content() == EMAIL.body


def test_long_unsubscribe_header_is_not_encoded() -> None:
    url = "http://localhost:8000/unsubscribe/" + "x" * 22 + "." + "y" * 22
    email = OutgoingEmail(**{**EMAIL.__dict__, "headers": {"List-Unsubscribe": f"<{url}>"}})
    raw = build_message(email).as_string()
    assert f"List-Unsubscribe: <{url}>" in raw
    assert "=?utf-8?" not in raw


async def test_smtp_sends_with_starttls_and_login(fake_smtp: type[_FakeSMTP]) -> None:
    provider = SmtpProvider("smtp.test", 587, username="u", password="p", starttls=True)
    result = await provider.send(EMAIL)
    [smtp] = fake_smtp.instances
    assert smtp.calls == ["starttls", "login:u"]
    assert len(smtp.sent) == 1
    assert result.provider_message_id == "<abc@example.com>"
    assert result.headers["Subject"] == EMAIL.subject


async def test_smtp_disabled_without_host() -> None:
    provider = SmtpProvider("", 25)
    assert not provider.enabled
    with pytest.raises(EmailDisabledError):
        await provider.send(EMAIL)


async def test_permanent_refusal_is_a_bounce(fake_smtp: type[_FakeSMTP]) -> None:
    fake_smtp.raise_on_send = smtplib.SMTPRecipientsRefused(
        {"grace@acme.test": (550, b"no such user")}
    )
    with pytest.raises(EmailRecipientRefusedError):
        await SmtpProvider("smtp.test", 25).send(EMAIL)


async def test_temporary_refusal_is_transient(fake_smtp: type[_FakeSMTP]) -> None:
    fake_smtp.raise_on_send = smtplib.SMTPRecipientsRefused(
        {"grace@acme.test": (451, b"try later")}
    )
    with pytest.raises(EmailTransientError):
        await SmtpProvider("smtp.test", 25).send(EMAIL)


async def test_network_error_is_transient(fake_smtp: type[_FakeSMTP]) -> None:
    fake_smtp.raise_on_send = ConnectionRefusedError("down")
    with pytest.raises(EmailTransientError):
        await SmtpProvider("smtp.test", 25).send(EMAIL)
