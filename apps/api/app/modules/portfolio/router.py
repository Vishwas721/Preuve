from fastapi import APIRouter

from app.core.deps import ActiveWorkspace, SessionDep
from app.modules.portfolio import service
from app.modules.portfolio.schemas import PortfolioItem

router = APIRouter(tags=["portfolio"])


@router.get("/portfolio", response_model=list[PortfolioItem])
async def get_portfolio(session: SessionDep, workspace_id: ActiveWorkspace) -> list[PortfolioItem]:
    """Every idea in the active workspace with its evidence and progress, most recent first."""
    return await service.portfolio(session, workspace_id)
