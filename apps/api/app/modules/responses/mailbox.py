"""Reading the sending mailbox over IMAP (stdlib `imaplib`, in a thread).

The folder is opened read-only and messages are fetched with BODY.PEEK, so polling never marks
anything as read. Only email newer than the first outreach send is looked at.
"""

import asyncio
import imaplib
import logging
from abc import ABC, abstractmethod
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.outreach import service as outreach
from app.modules.responses import service

logger = logging.getLogger(__name__)

MAX_PER_POLL = 200


class MailboxError(Exception):
    pass


class Mailbox(ABC):
    @property
    def enabled(self) -> bool:
        return True

    @abstractmethod
    async def fetch_since(self, since: date) -> list[bytes]:
        """Raw RFC 5322 emails received on or after `since`, oldest first."""


class ImapMailbox(Mailbox):
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        *,
        folder: str = "INBOX",
        ssl: bool = True,
        timeout_s: float = 30.0,
    ) -> None:
        self.host, self.port, self.folder, self.ssl = host, port, folder, ssl
        self.username, self.password, self.timeout_s = username, password, timeout_s

    @property
    def enabled(self) -> bool:
        return bool(self.host and self.username)

    @property
    def label(self) -> str:
        return (
            f"imap{'s' if self.ssl else ''}://{self.username}@{self.host}:{self.port}/{self.folder}"
        )

    async def fetch_since(self, since: date) -> list[bytes]:
        if not self.enabled:
            raise MailboxError("Mailbox polling is disabled: set IMAP_HOST in .env")
        return await asyncio.to_thread(self._fetch_sync, since)

    def _fetch_sync(self, since: date) -> list[bytes]:
        cls = imaplib.IMAP4_SSL if self.ssl else imaplib.IMAP4
        try:
            with cls(self.host, self.port, timeout=self.timeout_s) as imap:
                imap.login(self.username, self.password)
                status, _ = imap.select(self.folder, readonly=True)
                if status != "OK":
                    raise MailboxError(f"Can't open folder {self.folder}")
                status, data = imap.search(None, "SINCE", since.strftime("%d-%b-%Y"))
                if status != "OK":
                    raise MailboxError("IMAP search failed")
                ids = data[0].split()[-MAX_PER_POLL:]
                out: list[bytes] = []
                for num in ids:
                    status, parts = imap.fetch(num, "(BODY.PEEK[])")
                    if status == "OK":
                        out.extend(p[1] for p in parts if isinstance(p, tuple))
                return out
        except imaplib.IMAP4.error as exc:
            raise MailboxError(f"IMAP error: {exc}") from exc
        except OSError as exc:
            raise MailboxError(f"Can't reach the mailbox: {exc}") from exc


def get_mailbox(s: Settings) -> ImapMailbox:
    return ImapMailbox(
        s.imap_host,
        s.imap_port,
        s.imap_username,
        s.imap_password,
        folder=s.imap_folder,
        ssl=s.imap_ssl,
        timeout_s=s.imap_timeout_s,
    )


async def poll(session: AsyncSession, mailbox: Mailbox) -> dict[str, Any]:
    """Ingest new replies and bounces. Returns counts and the new response ids to analyze."""
    report: dict[str, Any] = {
        "at": datetime.now(UTC).isoformat(),
        "seen": 0,
        "reply": 0,
        "bounce": 0,
        "duplicate": 0,
        "unmatched": 0,
        "empty": 0,
        "errors": 0,
        "new_response_ids": [],
        "error": None,
    }
    first = await outreach.first_sent_at(session)
    if first is None:
        report["error"] = "Nothing sent yet."
        return report
    try:
        raws = await mailbox.fetch_since((first - timedelta(days=1)).date())
    except MailboxError as exc:
        report["error"] = str(exc)
        return report
    for raw in raws:
        report["seen"] += 1
        try:
            outcome, rid = await service.ingest_email(session, raw)
        except Exception:  # one bad email must not stop the poll
            logger.exception("could not ingest a mailbox email")
            await session.rollback()
            report["errors"] += 1
            continue
        report[outcome] += 1
        if rid is not None:
            report["new_response_ids"].append(str(rid))
    return report
