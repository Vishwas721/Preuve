import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ValidationState(enum.StrEnum):
    """PRD §25 validation states."""

    UNVALIDATED = "unvalidated"
    RESEARCHING = "researching"
    EARLY_SIGNAL = "early_signal"
    PROBLEM_VALIDATED = "problem_validated"
    SOLUTION_VALIDATION = "solution_validation"
    COMMERCIAL_VALIDATION = "commercial_validation"
    MVP_READY = "mvp_ready"


class Idea(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An idea under validation (PRD §8). Everything else in Preuve hangs off this."""

    __tablename__ = "ideas"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    target_market: Mapped[str] = mapped_column(String(100))
    why_it_matters: Mapped[str | None] = mapped_column(Text)

    # Optional context from the user (PRD §8).
    industry: Mapped[str | None] = mapped_column(String(200))
    customer_type: Mapped[str | None] = mapped_column(String(200))
    business_model: Mapped[str | None] = mapped_column(String(200))
    known_competitors: Mapped[str | None] = mapped_column(Text)
    assumptions: Mapped[str | None] = mapped_column(Text)

    state: Mapped[ValidationState] = mapped_column(
        Enum(
            ValidationState,
            native_enum=False,
            length=32,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=ValidationState.UNVALIDATED,
    )

    owner: Mapped["User"] = relationship(back_populates="ideas")  # noqa: F821
