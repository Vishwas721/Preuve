"""Import every ORM model here so `Base.metadata` is complete for Alembic."""

from app.db.base import Base

__all__ = ["Base"]
