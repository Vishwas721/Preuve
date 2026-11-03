"""Pure outreach-safety helpers (PRD §36): addresses, hashes, tokens, footer, draft checks."""

import base64
import hashlib
import hmac
import json
import re
import uuid

_EMAIL = re.compile(r"^[^@\s<>\"]+@[^@\s<>\"]+\.[^@\s<>\"]+$")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL.match(email.strip())) and len(email) <= 320


def approval_hash(to_email: str, subject: str, body: str) -> str:
    """What the human approved; the send job refuses a message whose hash has changed."""
    payload = json.dumps([normalize_email(to_email), subject, body], ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def content_hash(headers: dict[str, str], body: str) -> str:
    """Of the exact email sent; survives redaction so the record stays verifiable."""
    payload = json.dumps([sorted(headers.items()), body], ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


# ---------- unsubscribe tokens ----------


def _sig(secret: str, message_id: uuid.UUID) -> str:
    mac = hmac.new(secret.encode(), message_id.bytes, hashlib.sha256).digest()[:16]
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")


def unsubscribe_token(secret: str, message_id: uuid.UUID) -> str:
    mid = base64.urlsafe_b64encode(message_id.bytes).decode().rstrip("=")
    return f"{mid}.{_sig(secret, message_id)}"


def parse_unsubscribe_token(secret: str, token: str) -> uuid.UUID | None:
    """The message id a valid token was issued for, else None."""
    try:
        mid_part, sig = token.split(".", 1)
        message_id = uuid.UUID(
            bytes=base64.urlsafe_b64decode(mid_part + "=" * (-len(mid_part) % 4))
        )
    except (ValueError, TypeError):
        return None
    return message_id if hmac.compare_digest(sig, _sig(secret, message_id)) else None


# ---------- footer ----------


def footer(
    *, sender_name: str, purpose: str, unsubscribe_url: str, postal_address: str = ""
) -> str:
    """Transparent identity + opt-out, appended to every message exactly as sent."""
    lines = [
        "--",
        f"{sender_name}. {purpose.strip()}",
        "If you'd rather not hear from me, reply \"stop\" and I won't write again, or unsubscribe:",
        unsubscribe_url,
    ]
    if postal_address.strip():
        lines.append(postal_address.strip())
    return "\n".join(lines)


def full_body(body: str, footer_text: str) -> str:
    return f"{body.rstrip()}\n\n{footer_text}\n"


# ---------- draft checks (warnings shown to the human, never auto-fixes) ----------

_PRODUCT_CLAIMS = re.compile(
    r"\b(our (product|platform|tool|app|software|solution)|we('ve| have) built|"
    r"sign[ -]?up|free trial|book a demo|schedule a demo|a demo|pricing|discount|"
    r"buy now|limited time)\b",
    re.IGNORECASE,
)
_HYPE = re.compile(
    r"\b(revolutionary|game[- ]chang\w*|guarantee\w*|10x|best[- ]in[- ]class|"
    r"cutting[- ]edge|world[- ]class)\b",
    re.IGNORECASE,
)
MAX_WORDS = 150


def draft_checks(subject: str, body: str, to_name: str) -> list[str]:
    checks: list[str] = []
    if m := _PRODUCT_CLAIMS.search(f"{subject}\n{body}"):
        checks.append(f'Sounds like a sales pitch or an existing product ("{m.group(0)}").')
    if m := _HYPE.search(f"{subject}\n{body}"):
        checks.append(f'Exaggerated wording ("{m.group(0)}").')
    if body.count("?") > 1:
        checks.append("Asks more than one question; keep it to one small question.")
    if body.count("?") == 0 and body.strip():
        checks.append("Doesn't ask a question.")
    words = len(body.split())
    if words > MAX_WORDS:
        checks.append(f"Long for a cold research note ({words} words; aim for under {MAX_WORDS}).")
    first = to_name.split()[0] if to_name.strip() else ""
    if first and first.lower() not in body.lower():
        checks.append(f"Doesn't address {first} by name.")
    return checks
