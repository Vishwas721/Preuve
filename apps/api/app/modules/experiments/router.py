import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.deps import SessionDep
from app.modules.experiments import service
from app.modules.experiments.models import Experiment
from app.modules.experiments.schemas import ExperimentCreate, ExperimentRead, ExperimentUpdate
from app.modules.ideas.deps import OwnedIdea

router = APIRouter(prefix="/ideas/{idea_id}", tags=["experiments"])


async def _owned(session: SessionDep, idea_id: uuid.UUID, experiment_id: uuid.UUID) -> Experiment:
    row = await service.get_experiment(session, idea_id, experiment_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Experiment not found")
    return row


@router.get("/experiments", response_model=list[ExperimentRead])
async def list_experiments(idea: OwnedIdea, session: SessionDep) -> list[dict]:
    return [
        await service.read(session, r) for r in await service.list_experiments(session, idea.id)
    ]


@router.post("/experiments", response_model=ExperimentRead, status_code=status.HTTP_201_CREATED)
async def create_experiment(idea: OwnedIdea, data: ExperimentCreate, session: SessionDep) -> dict:
    try:
        row = await service.create(session, idea.id, data)
    except service.ExperimentError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return await service.read(session, row)


@router.get("/experiments/{experiment_id}", response_model=ExperimentRead)
async def get_experiment(idea: OwnedIdea, experiment_id: uuid.UUID, session: SessionDep) -> dict:
    return await service.read(session, await _owned(session, idea.id, experiment_id))


@router.patch("/experiments/{experiment_id}", response_model=ExperimentRead)
async def update_experiment(
    idea: OwnedIdea, experiment_id: uuid.UUID, data: ExperimentUpdate, session: SessionDep
) -> dict:
    row = await _owned(session, idea.id, experiment_id)
    try:
        row = await service.update(session, row, data)
    except service.ExperimentError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return await service.read(session, row)


@router.delete("/experiments/{experiment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_experiment(idea: OwnedIdea, experiment_id: uuid.UUID, session: SessionDep) -> None:
    await service.delete(session, await _owned(session, idea.id, experiment_id))
