"""Data-subject requests and the privacy check (Phase 5B), in the active workspace."""

import json
import uuid

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator

from app.core.deps import ActiveWorkspace, SessionDep
from app.modules.outreach import safety
from app.modules.privacy import service

router = APIRouter(prefix="/privacy", tags=["privacy"])


class EraseIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        if not safety.is_valid_email(v.strip()):
            raise ValueError("Not an email address")
        return v.strip().lower()


def _target(email: str | None, contact_id: uuid.UUID | None) -> dict:
    if contact_id is None and not (email and safety.is_valid_email(email.strip())):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Give an email address or a contact"
        )
    return {"email": email.strip() if email else None, "contact_id": contact_id}


@router.get("/people")
async def find_person(
    session: SessionDep,
    workspace_id: ActiveWorkspace,
    email: str | None = None,
    contact_id: uuid.UUID | None = None,
) -> dict:
    """What this workspace holds about a person (counts and contacts, no message bodies)."""
    found = await service.find(session, workspace_id, **_target(email, contact_id))
    return service.summary(found)


@router.get("/people/export")
async def export_person(
    session: SessionDep,
    workspace_id: ActiveWorkspace,
    email: str | None = None,
    contact_id: uuid.UUID | None = None,
) -> Response:
    """Everything about a person as a JSON file (access requests)."""
    found = await service.find(session, workspace_id, **_target(email, contact_id))
    data = await service.export(session, found)
    stamp = data["generated_at"][:10]
    return Response(
        json.dumps(data, indent=2, ensure_ascii=False, default=str),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="preuve-person-export-{stamp}.json"'
        },
    )


@router.post("/people/erase")
async def erase_person(data: EraseIn, session: SessionDep, workspace_id: ActiveWorkspace) -> dict:
    """Erase a person by email in this workspace; the address is suppressed and remembered (as
    a hash) so they aren't contacted or re-imported again."""
    return await service.erase(session, workspace_id, data.email)


@router.get("/check")
async def privacy_check(session: SessionDep, workspace_id: ActiveWorkspace) -> dict:
    findings = await service.check(session, workspace_id)
    return {"findings": findings, "ok": not findings}
