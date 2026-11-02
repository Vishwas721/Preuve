from fastapi import APIRouter

from app.core.deps import CurrentUser, SessionDep
from app.modules.portfolio import service
from app.modules.portfolio.schemas import PortfolioItem

router = APIRouter(tags=["portfolio"])


@router.get("/portfolio", response_model=list[PortfolioItem])
async def get_portfolio(session: SessionDep, user: CurrentUser) -> list[PortfolioItem]:
    """Every idea with its evidence balance and progress, most recently active first."""
    return await service.portfolio(session, user)
