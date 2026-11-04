import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.workspaces.models import Role


class AuthStatus(BaseModel):
    needs_setup: bool  # no account has a password yet: show first-run setup
    signup_open: bool  # ALLOW_SIGNUP (otherwise join by invitation only)
    signed_in: bool


_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


class SetupIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL.match(v):
            raise ValueError("Not an email address")
        return v


class InviteSignupIn(BaseModel):
    """Sign up through an invitation: the email is the invitation's."""

    name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class LoginIn(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=200)


class PasswordIn(BaseModel):
    current: str = Field(min_length=1, max_length=200)
    new: str = Field(min_length=1, max_length=200)


class WorkspaceSwitch(BaseModel):
    workspace_id: uuid.UUID


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str


class WorkspaceMembership(BaseModel):
    id: uuid.UUID
    name: str
    role: Role


class Me(BaseModel):
    user: UserRead
    workspaces: list[WorkspaceMembership]
    active_workspace_id: uuid.UUID | None
    via: str  # "session" | "token"


class TokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["research CLI"])


class TokenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    token_prefix: str
    workspace_id: uuid.UUID
    last_used_at: datetime | None
    created_at: datetime


class TokenCreated(TokenRead):
    token: str  # shown once
