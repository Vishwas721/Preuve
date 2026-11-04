"""Pure helpers for replies: quoted-history stripping, opt-outs, actions and email parsing."""

import html
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import getaddresses, parsedate_to_datetime

from app.modules.responses.prompts import Level, ResponseClassification, YesNo

# ---------- the reply itself, without the quoted history ----------

_HISTORY_MARKERS = [
    re.compile(r"^\s*On .{3,200}wrote:\s*$", re.IGNORECASE),  # Gmail / Apple Mail
    re.compile(r"^\s*Le .{3,200}a écrit\s*:\s*$", re.IGNORECASE),
    re.compile(r"^\s*-{2,}\s*Original Message\s*-{2,}\s*$", re.IGNORECASE),  # Outlook
    re.compile(r"^\s*-{2,}\s*Forwarded message\s*-{2,}\s*$", re.IGNORECASE),
    re.compile(r"^\s*From:\s.+$", re.IGNORECASE),  # Outlook header block
    re.compile(r"^\s*_{10,}\s*$"),
]


def strip_quoted(text: str) -> str:
    """The new part of a reply: stop at the quoted history, drop ">" lines."""
    kept: list[str] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if any(m.match(line) for m in _HISTORY_MARKERS):
            break
        if line.lstrip().startswith(">"):
            continue
        kept.append(line.rstrip())
    return "\n".join(kept).strip()


# ---------- opt-outs (PRD §36) ----------

_OPT_OUT = re.compile(
    r"\b(unsubscribe|remove me|take me off|opt[ -]?out|"
    r"stop (emailing|e-mailing|contacting|writing|messaging|sending)|"
    r"(do not|don't|dont|please don't|please do not) (contact|email|e-mail|write to|message)"
    r" me)\b",
    re.IGNORECASE,
)
# "stop" on its own first line, e.g. "STOP" or "Please stop."
_BARE_STOP = re.compile(r"^\s*(please\s+)?stop\s*[.!]*\s*$", re.IGNORECASE)
OPT_OUT_WINDOW = 200  # characters from the start of the reply


def is_opt_out(reply: str) -> bool:
    """A clear opt-out near the start of the reply. "stop" counts only on its own, so "I can't
    stop thinking about it" is not an opt-out."""
    head = reply.strip()[:OPT_OUT_WINDOW]
    if not head:
        return False
    first_line = head.splitlines()[0]
    return bool(_BARE_STOP.match(first_line) or _OPT_OUT.search(head))


# ---------- recommended action (deterministic, explainable) ----------


def recommended_action(c: ResponseClassification, opt_out: bool) -> tuple[str, str]:
    """(action, reason) from the labels. Never recommends contacting someone who opted out."""
    if opt_out:
        return "none", "They asked not to be contacted."
    if c.interest.value == Level.HIGH:
        return "interview", "They showed high interest."
    if c.problem_confirmed.value == YesNo.YES:
        return "interview", "They confirmed the problem."
    if c.problem_confirmed.value == YesNo.NO or c.interest.value == Level.LOW:
        return "close", "They don't have the problem or aren't interested."
    if c.sentiment.value == "negative":
        return "close", "The reply is negative."
    return "follow_up", "Nothing decisive yet; one follow-up question may help."


# ---------- email parsing ----------

_OUR_ID = re.compile(
    r"<([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})@[^>\s]+>", re.IGNORECASE
)
_TAGS = re.compile(r"<[^>]+>")
_BLOCK_TAGS = re.compile(r"</?(p|div|br|li|tr|h\d)[^>]*>", re.IGNORECASE)


def parse(raw: bytes) -> EmailMessage:
    return message_from_bytes(raw, policy=policy.default)  # type: ignore[return-value]


def referenced_ids(headers: str) -> list[uuid.UUID]:
    """Our outreach message ids (`<uuid@domain>`) found in In-Reply-To / References / a DSN."""
    out: list[uuid.UUID] = []
    for m in _OUR_ID.finditer(headers or ""):
        mid = uuid.UUID(m.group(1))
        if mid not in out:
            out.append(mid)
    return out


def sender(msg: EmailMessage) -> tuple[str, str | None]:
    pairs = getaddresses([str(msg.get("From", ""))])
    if not pairs:
        return "", None
    name, addr = pairs[0]
    return name.strip(), (addr.strip().lower() or None)


def received_at(msg: EmailMessage) -> datetime:
    try:
        dt = parsedate_to_datetime(str(msg.get("Date", "")))
    except (TypeError, ValueError):
        return datetime.now(UTC)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def body_text(msg: EmailMessage) -> str:
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    content = part.get_content()
    if part.get_content_subtype() == "html":
        content = html.unescape(_TAGS.sub("", _BLOCK_TAGS.sub("\n", content)))
    return content


@dataclass(frozen=True)
class Bounce:
    message_ids: list[uuid.UUID]
    recipient: str | None


def bounce_report(msg: EmailMessage, raw: bytes) -> Bounce | None:
    """A failed delivery-status report (RFC 3464) about one of our messages, else None."""
    if msg.get_content_type() != "multipart/report":
        return None
    if msg.get_param("report-type", header="content-type") != "delivery-status":
        return None
    text = raw.decode("utf-8", errors="replace")
    failed = re.search(r"^Action:\s*failed", text, re.IGNORECASE | re.MULTILINE) or re.search(
        r"^Status:\s*5\.", text, re.MULTILINE
    )
    if not failed:
        return None
    rcpt = re.search(r"^Final-Recipient:\s*rfc822;\s*(\S+)", text, re.IGNORECASE | re.MULTILINE)
    return Bounce(referenced_ids(text), rcpt.group(1).strip().lower() if rcpt else None)
