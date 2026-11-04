import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.responses.models import ResponseChannel, ResponseStatus


class ResponsePaste(BaseModel):
    """A reply pasted by the user. Link it to the outreach message it answers, if any."""

    text: str = Field(min_length=1, max_length=20000)
    message_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    from_name: str = Field(default="", max_length=200)
    from_email: str | None = Field(default=None, max_length=320)
    received_at: datetime | None = None


class ResponseSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    idea_id: uuid.UUID
    message_id: uuid.UUID | None
    contact_id: uuid.UUID | None
    company_id: uuid.UUID | None
    from_name: str
    from_email: str | None
    subject: str
    received_at: datetime
    channel: ResponseChannel
    status: ResponseStatus
    opt_out: bool
    classification: dict[str, Any] | None
    error: str | None
    created_at: datetime


class ResponseRead(ResponseSummary):
    raw_text: str
    dropped: list[dict[str, Any]]
    analyzed_at: datetime | None
    company_name: str | None = None
    original: dict[str, Any] | None = None  # the outreach message it answers
    evidence_ids: list[uuid.UUID] = []


class InboxStatus(BaseModel):
    enabled: bool
    mailbox: str
    last_poll: dict[str, Any] | None


class Dashboard(BaseModel):
    sent: int
    replies: int
    reply_rate: float | None
    positive: int
    neutral: int
    negative: int
    opt_outs: int
    problem_confirmed: int
    interview_recommended: int
    interviews_done: int
    pilot_or_better: int
    stated_strong: int
    top_pains: list[dict[str, Any]]
    frequencies: list[dict[str, Any]]
    current_solutions: list[dict[str, Any]]
