"""Experiments (PRD §28): a hypothesis tested on one or two cohorts of sent outreach.

Results are counted from stored messages and replies; the conclusion is written by the user.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ExperimentStatus(enum.StrEnum):
    RUNNING = "running"
    CONCLUDED = "concluded"


class Experiment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "experiments"

    idea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ideas.id", ondelete="CASCADE"), index=True
    )
    hypothesis: Mapped[str] = mapped_column(Text)
    # Cohort filters: {"label", "campaign_ids", "icp_id", "role_contains"} (see schemas.Cohort)
    cohort_a: Mapped[dict] = mapped_column(JSON)
    cohort_b: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[ExperimentStatus] = mapped_column(
        Enum(
            ExperimentStatus,
            native_enum=False,
            length=16,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=ExperimentStatus.RUNNING,
    )
    # Frozen when concluded, so later outreach doesn't rewrite a finished experiment.
    result: Mapped[dict | None] = mapped_column(JSON)
    conclusion: Mapped[str] = mapped_column(Text, default="")
    concluded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
