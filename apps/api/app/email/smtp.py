import asyncio
import smtplib
from datetime import UTC, datetime
from email.headerregistry import Address
from email.message import EmailMessage
from email.policy import default as default_policy
from email.utils import format_datetime

from app.email.base import (
    EmailDisabledError,
    EmailProvider,
    EmailRecipientRefusedError,
    EmailTransientError,
    OutgoingEmail,
    SendResult,
)

# Long URL headers (List-Unsubscribe) must stay plain ASCII: with the default 78-column limit
# Python RFC 2047-encodes them, and mail clients can no longer read the link. 998 is RFC 5322's
# hard limit.
POLICY = default_policy.clone(max_line_length=998)


def build_message(email: OutgoingEmail) -> EmailMessage:
    msg = EmailMessage(policy=POLICY)
    msg["From"] = Address(email.from_name, addr_spec=email.from_address)
    msg["To"] = Address(email.to_name, addr_spec=email.to_address)
    msg["Subject"] = email.subject
    msg["Date"] = format_datetime(datetime.now(UTC))
    msg["Message-ID"] = email.message_id
    for k, v in email.headers.items():
        msg[k] = v
    msg.set_content(email.body)
    return msg


class SmtpProvider(EmailProvider):
    """Plain SMTP (Mailpit in dev, a Gmail app password for real sends). stdlib, in a thread."""

    name = "smtp"

    def __init__(
        self,
        host: str,
        port: int,
        *,
        username: str = "",
        password: str = "",
        starttls: bool = False,
        ssl: bool = False,
        timeout_s: float = 30.0,
    ) -> None:
        self.host, self.port = host, port
        self.username, self.password = username, password
        self.starttls, self.ssl, self.timeout_s = starttls, ssl, timeout_s

    @property
    def enabled(self) -> bool:
        return bool(self.host)

    async def send(self, email: OutgoingEmail) -> SendResult:
        if not self.enabled:
            raise EmailDisabledError("Sending is disabled: set SMTP_HOST in .env")
        msg = build_message(email)
        await asyncio.to_thread(self._send_sync, msg)
        return SendResult(
            provider_message_id=email.message_id,
            headers={k: str(v) for k, v in msg.items()},
        )

    def _send_sync(self, msg: EmailMessage) -> None:
        cls = smtplib.SMTP_SSL if self.ssl else smtplib.SMTP
        try:
            with cls(self.host, self.port, timeout=self.timeout_s) as smtp:
                if self.starttls and not self.ssl:
                    smtp.starttls()
                if self.username:
                    smtp.login(self.username, self.password)
                smtp.send_message(msg)
        except smtplib.SMTPRecipientsRefused as exc:
            codes = [code for code, _ in exc.recipients.values()]
            if all(500 <= c < 600 for c in codes):
                raise EmailRecipientRefusedError(f"Recipient refused: {exc.recipients}") from exc
            raise EmailTransientError(f"Recipient temporarily refused: {exc.recipients}") from exc
        except smtplib.SMTPAuthenticationError as exc:
            raise EmailDisabledError(f"SMTP login failed: {exc.smtp_code}") from exc
        except (smtplib.SMTPException, OSError) as exc:
            raise EmailTransientError(f"SMTP error: {exc}") from exc
