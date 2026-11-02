from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.modules.analysis.router import router as analysis_router
from app.modules.competitors.router import router as competitors_router
from app.modules.ideas.router import router as ideas_router
from app.modules.meta.router import router as meta_router
from app.modules.portfolio.router import router as portfolio_router
from app.modules.prospects.router import router as prospects_router
from app.modules.research.router import router as research_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    pool = getattr(app.state, "arq", None)  # created lazily by get_job_queue
    if pool is not None:
        await pool.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(meta_router)
    app.include_router(ideas_router)
    app.include_router(analysis_router)
    app.include_router(research_router)
    app.include_router(competitors_router)
    app.include_router(prospects_router)
    app.include_router(portfolio_router)
    return app


app = create_app()
