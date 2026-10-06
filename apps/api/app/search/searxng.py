from datetime import datetime

import httpx

from app.search.base import SearchError, SearchProvider, SearchResult


class SearXNGProvider(SearchProvider):
    """Self-hosted SearXNG metasearch (infra/docker-compose.yml), JSON output."""

    name = "searxng"

    def __init__(
        self,
        base_url: str,
        *,
        timeout_s: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout_s, transport=transport)

    async def search(
        self, query: str, *, max_results: int = 10, language: str = "en-US"
    ) -> list[SearchResult]:
        params = {"q": query, "format": "json", "language": language, "safesearch": 0}
        try:
            resp = await self._client.get("/search", params=params)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise SearchError(f"SearXNG search failed: {exc}") from exc

        results: list[SearchResult] = []
        seen: set[str] = set()
        for item in resp.json().get("results", []):
            url = item.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            results.append(
                SearchResult(
                    url=url,
                    title=item.get("title") or url,
                    snippet=item.get("content") or "",
                    engine=item.get("engine"),
                    published_at=_parse_date(item.get("publishedDate")),
                )
            )
            if len(results) >= max_results:
                break
        return results


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
