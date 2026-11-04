import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.auth.schemas import _EMAIL
from app.modules.workspaces.models import Role


class WorkspaceIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    created_at: datetime


class MemberRead(BaseModel):
    user_id: uuid.UUID
    name: str
    email: str
    role: Role
    joined_at: datetime


class RoleIn(BaseModel):
    role: Role


class InvitationIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: Role = Role.MEMBER

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL.match(v):
            raise ValueError("Not an email address")
        return v


class InvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: Role
    expires_at: datetime
    created_at: datetime


class InvitationCreated(InvitationRead):
    token: str  # shown once; the web app turns it into a link


class InvitationPublic(BaseModel):
    """What someone opening an invitation link may see."""

    workspace_name: str
    email: str
    role: Role
    expires_at: datetime
    account_exists: bool  # sign in to accept, or sign up
