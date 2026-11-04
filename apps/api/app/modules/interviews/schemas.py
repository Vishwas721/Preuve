import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.interviews.models import InterviewStatus, JobState, NoteKind


class InterviewCreate(BaseModel):
    contact_id: uuid.UUID | None = None
    response_id: uuid.UUID | None = None
    interviewee_name: str = Field(default="", max_length=200)
    interviewee_role: str = Field(default="", max_length=200)
    company_name: str = Field(default="", max_length=200)
    scheduled_at: datetime | None = None
    scheduling_note: str = Field(default="", max_length=2000)


class InterviewUpdate(BaseModel):
    interviewee_name: str | None = Field(default=None, min_length=1, max_length=200)
    interviewee_role: str | None = Field(default=None, max_length=200)
    company_name: str | None = Field(default=None, max_length=200)
    scheduled_at: datetime | None = None
    status: InterviewStatus | None = None
    scheduling_note: str | None = Field(default=None, max_length=2000)


class NoteCreate(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    kind: NoteKind = NoteKind.LIVE


class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: NoteKind
    text: str
    created_at: datetime


class InterviewSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    idea_id: uuid.UUID
    contact_id: uuid.UUID | None
    company_id: uuid.UUID | None
    response_id: uuid.UUID | None
    interviewee_name: str
    interviewee_role: str
    company_name: str
    scheduled_at: datetime | None
    status: InterviewStatus
    guide_state: JobState
    extraction_state: JobState
    created_at: datetime
    updated_at: datetime


class InterviewRead(InterviewSummary):
    scheduling_note: str
    guide: dict[str, Any] | None
    extraction: dict[str, Any] | None
    dropped: list[dict[str, Any]]
    error: str | None
    notes: list[NoteRead] = []
    evidence_ids: list[uuid.UUID] = []
