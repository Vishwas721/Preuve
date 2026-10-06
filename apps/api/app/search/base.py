from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel


class SearchError(Exception):
    """Search provider unreachable or returned an error."""


class SearchResult(BaseModel):
    url: str
    title: str
    snippet: str = ""
    engine: str | None = None
    published_at: datetime | None = None


class SearchProvider(ABC):
    name: str

    @abstractmethod
    async def search(
        self, query: str, *, max_results: int = 10, language: str = "en-US"
    ) -> list[SearchResult]: ...
