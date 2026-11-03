import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.llm.guardrails import Claim
from app.modules.outreach.models import (
    CampaignStatus,
    EmailSource,
    MessageStatus,
    SuppressionReason,
)

# ---------- campaigns ----------


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    purpose: str = Field(min_length=10, max_length=600)
    icp_id: uuid.UUID | None = None
    daily_limit: int = Field(default=10, ge=1, le=50)


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    purpose: str | None = Field(default=None, min_length=10, max_length=600)
    daily_limit: int | None = Field(default=None, ge=1, le=50)
    status: CampaignStatus | None = None


class CampaignStats(BaseModel):
    drafting: int = 0
    draft: int = 0
    approved: int = 0
    rejected: int = 0
    sent: int = 0
    bounced: int = 0
    blocked: int = 0
    sent_today: int = 0


class CampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    idea_id: uuid.UUID
    icp_id: uuid.UUID | None
    name: str
    purpose: str
    daily_limit: int
    status: CampaignStatus
    created_at: datetime
    stats: CampaignStats


# ---------- messages ----------


class DraftRequest(BaseModel):
    contact_ids: list[uuid.UUID] = Field(min_length=1, max_length=25)


class DraftSkip(BaseModel):
    contact_id: uuid.UUID
    reason: str


class DraftResult(BaseModel):
    created: list[uuid.UUID]
    skipped: list[DraftSkip]


class MessageUpdate(BaseModel):
    to_email: str | None = Field(default=None, max_length=320)
    subject: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, max_length=5000)


class SendRequest(BaseModel):
    message_ids: list[uuid.UUID] | None = None


class MessageSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    campaign_id: uuid.UUID
    contact_id: uuid.UUID | None
    company_id: uuid.UUID | None
    to_name: str
    to_email: str | None
    subject: str
    status: MessageStatus
    checks: list[str]
    approved_at: datetime | None
    sent_at: datetime | None
    updated_at: datetime


class CitedEvidence(BaseModel):
    id: uuid.UUID
    quote: str
    statement: str
    url: str
    fetched_at: datetime
    verification: str
    stance: str


class MessageProspect(BaseModel):
    company_id: uuid.UUID
    name: str
    domain: str
    score: int | None
    contact_role: str | None
    contact_source_url: str | None


class MessageRead(MessageSummary):
    to_email_source: EmailSource | None
    body: str
    why_selected: list[Claim]
    cited_evidence_ids: list[str]
    draft_error: str | None
    user_edited: bool
    rejected_at: datetime | None
    sent_body: str | None
    sent_headers: dict | None
    content_hash: str | None
    provider_message_id: str | None
    send_error: str | None
    blocked_reason: str | None
    bounced_at: datetime | None
    redacted_at: datetime | None
    stale: bool = False  # stuck in `drafting` (lost job); can be redrafted
    prospect: MessageProspect | None = None
    cited_evidence: list[CitedEvidence] = []


class SendQueued(BaseModel):
    queued: int


# ---------- suppressions ----------


class SuppressionCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    note: str | None = Field(default=None, max_length=500)


class SuppressionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    reason: SuppressionReason
    message_id: uuid.UUID | None
    note: str | None
    created_at: datetime


# ---------- recipients & settings ----------


class Recipient(BaseModel):
    contact_id: uuid.UUID
    name: str
    role: str
    email: str | None
    company_id: uuid.UUID
    company_name: str
    score: int | None
    prospect_status: str
    suppressed: bool
    campaign_ids: list[uuid.UUID]  # campaigns that already have a message for this contact


class OutreachSettings(BaseModel):
    sending_enabled: bool
    provider: str
    sender_name: str
    sender_address: str
    sender_ready: bool  # name and address configured
    daily_limit: int
    cooldown_days: int
    sent_today: int
    postal_address: str
