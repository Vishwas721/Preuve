"""Email provider interface (Phase 2). Domain code builds an `OutgoingEmail`; providers send it."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class EmailError(Exception):
    """Base class for send failures."""


class EmailDisabledError(EmailError):
    """No provider configured (e.g. SMTP_HOST is empty)."""


class EmailTransientError(EmailError):
    """Temporary failure (network, 4xx); the message can be retried later."""


class EmailRecipientRefusedError(EmailError):
    """The server permanently refused the recipient: record a bounce."""


@dataclass(frozen=True)
class OutgoingEmail:
    from_name: str
    from_address: str
    to_name: str
    to_address: str
    subject: str
    body: str  # plain text, exactly as sent
    message_id: str  # RFC 5322 Message-ID, e.g. <uuid@domain>
    headers: dict[str, str] = field(default_factory=dict)  # extra headers (List-Unsubscribe…)


@dataclass(frozen=True)
class SendResult:
    provider_message_id: str
    headers: dict[str, str]  # every header actually sent


class EmailProvider(ABC):
    name: str

    @property
    def enabled(self) -> bool:
        return True

    @abstractmethod
    async def send(self, email: OutgoingEmail) -> SendResult:
        """Send one email, or raise an `EmailError` subclass."""
