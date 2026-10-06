"""Import every ORM model here so `Base.metadata` is complete for Alembic."""

from app.db.base import Base
from app.modules.ideas.models import Idea
from app.modules.users.models import User

__all__ = ["Base", "Idea", "User"]
