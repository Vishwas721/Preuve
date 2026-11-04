import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.wtp.models import Commitment, StatedWillingness, WtpSource


class WtpCreate(BaseModel):
    customer_label: str = Field(min_length=1, max_length=300)
    contact_id: uuid.UUID | None = None
    current_spend: str = Field(default="", max_length=500)
    problem_cost: str = Field(default="", max_length=500)
    expected_price: str = Field(default="", max_length=500)
    stated_willingness: StatedWillingness = StatedWillingness.UNKNOWN
    stated_quote: str = Field(default="", max_length=2000)
    commitment: Commitment = Commitment.NONE
    commitment_note: str = Field(default="", max_length=2000)
    committed_at: datetime | None = None


class WtpUpdate(BaseModel):
    customer_label: str | None = Field(default=None, min_length=1, max_length=300)
    current_spend: str | None = Field(default=None, max_length=500)
    problem_cost: str | None = Field(default=None, max_length=500)
    expected_price: str | None = Field(default=None, max_length=500)
    stated_willingness: StatedWillingness | None = None
    stated_quote: str | None = Field(default=None, max_length=2000)
    commitment: Commitment | None = None
    commitment_note: str | None = Field(default=None, max_length=2000)
    committed_at: datetime | None = None


class WtpRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    idea_id: uuid.UUID
    contact_id: uuid.UUID | None
    company_id: uuid.UUID | None
    response_id: uuid.UUID | None
    interview_id: uuid.UUID | None
    customer_label: str
    current_spend: str
    problem_cost: str
    expected_price: str
    stated_willingness: StatedWillingness
    stated_quote: str
    stated_evidence_id: uuid.UUID | None
    commitment: Commitment
    commitment_note: str
    committed_at: datetime | None
    source: WtpSource
    created_at: datetime
    updated_at: datetime
