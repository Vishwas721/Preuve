from app.email.base import EmailProvider, OutgoingEmail, SendResult
from app.email.smtp import build_message


class FakeEmailProvider(EmailProvider):
    """Records sends for tests. Queue exceptions in `fail_with` (by address) to simulate errors."""

    name = "fake"

    def __init__(self, *, enabled: bool = True) -> None:
        self._enabled = enabled
        self.sent: list[OutgoingEmail] = []
        self.fail_with: dict[str, Exception] = {}

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def send(self, email: OutgoingEmail) -> SendResult:
        if email.to_address in self.fail_with:
            raise self.fail_with[email.to_address]
        self.sent.append(email)
        msg = build_message(email)
        return SendResult(email.message_id, {k: str(v) for k, v in msg.items()})
