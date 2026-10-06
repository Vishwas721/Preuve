from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session
from app.modules.users.models import User
from app.modules.users.service import get_or_create_user

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(session: SessionDep) -> User:
    """Single-user mode until Phase 5. This is the one seam to replace with real auth."""
    settings = get_settings()
    return await get_or_create_user(session, settings.dev_user_email, settings.dev_user_name)


CurrentUser = Annotated[User, Depends(get_current_user)]
