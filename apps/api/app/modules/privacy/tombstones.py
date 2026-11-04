"""Tombstones for deleted people. Kept free of other module imports so the research import and
the prospects module can use it without import cycles."""

import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.privacy.models import DeletedPerson


def _h(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def email_hash(email: str) -> str:
    return _h(email.strip().lower())


def person_hash(domain: str, name_key: str) -> str:
    return _h(f"{domain.strip().lower()}|{name_key}")


async def record(
    session: AsyncSession,
    *,
    emails: set[str] | None = None,
    domain: str | None = None,
    name_key: str | None = None,
    workspace_id: uuid.UUID | None = None,
    reason: str = "deletion_request",
) -> None:
    """Remember a deletion (does not commit). Idempotent per hash."""
    wanted: list[tuple[str | None, str | None]] = [
        (email_hash(e), None) for e in emails or set() if e
    ]
    if domain and name_key:
        wanted.append((None, person_hash(domain, name_key)))
    for eh, ph in wanted:
        column = DeletedPerson.email_hash if eh else DeletedPerson.person_hash
        if await session.scalar(select(DeletedPerson.id).where(column == (eh or ph)).limit(1)):
            continue
        session.add(
            DeletedPerson(email_hash=eh, person_hash=ph, workspace_id=workspace_id, reason=reason)
        )
    await session.flush()


async def is_deleted(
    session: AsyncSession,
    *,
    email: str | None = None,
    domain: str | None = None,
    name_key: str | None = None,
) -> bool:
    conds = []
    if email:
        conds.append(DeletedPerson.email_hash == email_hash(email))
    if domain and name_key:
        conds.append(DeletedPerson.person_hash == person_hash(domain, name_key))
    for cond in conds:
        if await session.scalar(select(DeletedPerson.id).where(cond).limit(1)):
            return True
    return False
