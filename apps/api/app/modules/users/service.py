from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User


async def get_or_create_user(session: AsyncSession, email: str, name: str) -> User:
    user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, name=name)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user
