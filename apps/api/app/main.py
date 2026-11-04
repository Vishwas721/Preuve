from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.deps import get_principal
from app.core.middleware import BodySizeLimitMiddleware, SecurityHeadersMiddleware
from app.core.ratelimit import limit_private, limit_public
from app.modules.analysis.router import router as analysis_router
from app.modules.auth.router import admin_router, reset_public_router
from app.modules.auth.router import public_router as auth_public_router
from app.modules.auth.router import router as auth_router
from app.modules.competitors.router import router as competitors_router
from app.modules.experiments.router import router as experiments_router
from app.modules.ideas.router import router as ideas_router
from app.modules.interviews.router import router as interviews_router
from app.modules.meta.router import router as meta_router
from app.modules.outreach.router import global_router as outreach_global_router
from app.modules.outreach.router import public_router as unsubscribe_router
from app.modules.outreach.router import router as outreach_router
from app.modules.portfolio.router import router as portfolio_router
from app.modules.privacy.router import router as privacy_router
from app.modules.prospects.router import router as prospects_router
from app.modules.reports.router import router as reports_router
from app.modules.research.router import router as research_router
from app.modules.responses.router import inbox_router
from app.modules.responses.router import router as responses_router
from app.modules.validation.router import router as validation_router
from app.modules.workspaces.router import public_router as invitations_public_router
from app.modules.workspaces.router import router as workspaces_router
from app.modules.wtp.router import router as wtp_router

# Reachable without signing in. Everything else requires a session or an API token.
PUBLIC_ROUTERS = [
    meta_router,  # /health
    unsubscribe_router,  # recipients clicking the unsubscribe link
    auth_public_router,  # status, setup, sign-up, login, logout
    invitations_public_router,  # opening an invitation link, signing up with it
    reset_public_router,  # opening a password-reset link, setting the password
]

PRIVATE_ROUTERS = [
    auth_router,
    admin_router,
    workspaces_router,
    ideas_router,
    analysis_router,
    research_router,
    competitors_router,
    prospects_router,
    portfolio_router,
    outreach_router,
    outreach_global_router,
    responses_router,
    inbox_router,
    interviews_router,
    wtp_router,
    validation_router,
    experiments_router,
    reports_router,
    privacy_router,
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    pool = getattr(app.state, "arq", None)  # created lazily by get_job_queue
    if pool is not None:
        await pool.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    dev = settings.environment == "development"
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
        # Interactive docs and the schema only in development (Phase 5C).
        docs_url="/docs" if dev else None,
        redoc_url="/redoc" if dev else None,
        openapi_url="/openapi.json" if dev else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Outermost last: sizes are checked before anything else runs; headers go on every reply.
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_bytes)
    app.add_middleware(SecurityHeadersMiddleware, hsts=not dev)

    for r in PUBLIC_ROUTERS:
        app.include_router(r, dependencies=[Depends(limit_public)])
    # Default-deny: a route added to these routers is private even if it forgets to ask for
    # the caller. (Routes that need the caller still declare it to get the Principal.)
    for r in PRIVATE_ROUTERS:
        app.include_router(r, dependencies=[Depends(get_principal), Depends(limit_private)])
    return app


app = create_app()
