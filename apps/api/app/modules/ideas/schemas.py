import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.ideas.models import ValidationState


class IdeaBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, description="The idea in the founder's words.")
    target_market: str = Field(min_length=1, max_length=100, examples=["United States"])
    why_it_matters: str | None = None
    industry: str | None = Field(default=None, max_length=200)
    customer_type: str | None = Field(default=None, max_length=200)
    business_model: str | None = Field(default=None, max_length=200)
    known_competitors: str | None = None
    assumptions: str | None = None


class IdeaCreate(IdeaBase):
    pass


class IdeaUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1)
    target_market: str | None = Field(default=None, min_length=1, max_length=100)
    why_it_matters: str | None = None
    industry: str | None = Field(default=None, max_length=200)
    customer_type: str | None = Field(default=None, max_length=200)
    business_model: str | None = Field(default=None, max_length=200)
    known_competitors: str | None = None
    assumptions: str | None = None


class IdeaRead(IdeaBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    state: ValidationState
    created_at: datetime
    updated_at: datetime
