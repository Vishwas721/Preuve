import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.deps import SessionDep
from app.modules.ideas.deps import OwnedIdea
from app.modules.wtp import service
from app.modules.wtp.models import WtpSignal
from app.modules.wtp.schemas import WtpCreate, WtpRead, WtpUpdate

router = APIRouter(prefix="/ideas/{idea_id}", tags=["wtp"])


async def _owned(session: SessionDep, idea_id: uuid.UUID, signal_id: uuid.UUID) -> WtpSignal:
    row = await service.get_signal(session, idea_id, signal_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Record not found")
    return row


@router.get("/wtp", response_model=list[WtpRead])
async def list_signals(idea: OwnedIdea, session: SessionDep) -> list:
    return await service.list_signals(session, idea.id)


@router.post("/wtp", response_model=WtpRead, status_code=status.HTTP_201_CREATED)
async def create_signal(idea: OwnedIdea, data: WtpCreate, session: SessionDep) -> WtpSignal:
    try:
        row = await service.create(session, idea.id, data)
    except service.WtpError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    await session.refresh(row)
    return row


@router.patch("/wtp/{signal_id}", response_model=WtpRead)
async def update_signal(
    idea: OwnedIdea, signal_id: uuid.UUID, data: WtpUpdate, session: SessionDep
) -> WtpSignal:
    row = await service.update(session, await _owned(session, idea.id, signal_id), data)
    await session.refresh(row)
    return row


@router.delete("/wtp/{signal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_signal(idea: OwnedIdea, signal_id: uuid.UUID, session: SessionDep) -> None:
    await service.delete_signal(session, await _owned(session, idea.id, signal_id))
