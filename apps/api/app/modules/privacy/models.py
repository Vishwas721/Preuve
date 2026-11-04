"""Deletion tombstones (Phase 5B): remember *that* someone was deleted without keeping who.

Only SHA-256 hashes are stored, so a later research import can recognise the person and skip
them, but the table itself holds no readable personal data.
"""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DeletedPerson(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "deleted_people"

    # sha256 of the lower-cased email address
    email_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    # sha256 of "<company domain>|<contact name key>"
    person_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    reason: Mapped[str] = mapped_column(String(50), default="deletion_request")
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="SET NULL")
    )
