import httpx
import pytest

from app.search.fetch import FetchError, PageFetcher
from app.search.searxng import SearXNGProvider

HTML = """<html><head><title>Weekly reports are painful</title></head><body>
<article><h1>Weekly reports are painful</h1>
<p>Our project coordinators spend most of Friday compiling weekly progress reports
from site photos, spreadsheets and emails. It is entirely manual and error prone,
and every project manager on the team complains about it constantly.</p>
<p>We have tried several tools but none of them fit how our sites actually work.</p>
</article></body></html>"""


async def test_searxng_parses_dedupes_and_limits() -> None:
    payload = {
        "results": [
            {"url": "https://a.com", "title": "A", "content": "snippet a", "engine": "ddg"},
            {"url": "https://a.com", "title": "A dup"},
            {"url": "https://b.com", "title": "B", "publishedDate": "2026-01-02T00:00:00"},
            {"url": "https://c.com", "title": "C"},
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["format"] == "json"
        return httpx.Response(200, json=payload)

    provider = SearXNGProvider("http://searx", transport=httpx.MockTransport(handler))
    results = await provider.search("q", max_results=2)
    assert [r.url for r in results] == ["https://a.com", "https://b.com"]
    assert results[0].snippet == "snippet a"
    assert results[1].published_at is not None


def _site(robots: str) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=robots)
        return httpx.Response(200, text=HTML, headers={"content-type": "text/html"})

    return httpx.MockTransport(handler)


async def test_fetch_extracts_text_with_provenance() -> None:
    fetcher = PageFetcher(transport=_site("User-agent: *\nAllow: /"))
    page = await fetcher.fetch("https://example.com/post")
    assert "weekly progress reports" in page.text
    assert page.final_url == "https://example.com/post"
    assert page.fetched_at.tzinfo is not None


async def test_fetch_respects_robots() -> None:
    fetcher = PageFetcher(transport=_site("User-agent: *\nDisallow: /"))
    with pytest.raises(FetchError, match="robots"):
        await fetcher.fetch("https://example.com/post")


async def test_fetch_rejects_non_http() -> None:
    with pytest.raises(FetchError):
        await PageFetcher().fetch("file:///etc/passwd")
