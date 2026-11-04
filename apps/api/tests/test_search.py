import httpx
import pytest

from app.search.fetch import MAX_BYTES, BlockedDestinationError, FetchError, PageFetcher
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


async def public(host: str) -> list[str]:
    """Tests never touch DNS: every name resolves to a public documentation-free address."""
    return ["93.184.215.14"]


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
    assert "Weekly reports are painful" in page.full_text
    assert len(page.content_hash) == 64


async def test_fetch_respects_robots() -> None:
    fetcher = PageFetcher(transport=_site("User-agent: *\nDisallow: /"))
    with pytest.raises(FetchError, match="robots"):
        await fetcher.fetch("https://example.com/post")


async def test_fetch_rejects_non_http() -> None:
    with pytest.raises(FetchError):
        await PageFetcher(resolver=public).fetch("file:///etc/passwd")


# ---------- SSRF guard (Phase 5C) ----------


def _never(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"must not be requested: {request.url}")


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://localhost:8000/ideas",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://100.64.0.1/",
        "http://0.0.0.0/",
        "https://example.com:5435/",
    ],
)
async def test_private_and_odd_destinations_are_refused(url: str) -> None:
    async def resolver(host: str) -> list[str]:
        return {"localhost": ["127.0.0.1", "::1"]}.get(host, ["93.184.215.14"])

    fetcher = PageFetcher(transport=httpx.MockTransport(_never), resolver=resolver)
    with pytest.raises(BlockedDestinationError):
        await fetcher.fetch(url)


async def test_a_name_resolving_to_any_private_address_is_refused() -> None:
    async def resolver(host: str) -> list[str]:
        return ["93.184.215.14", "10.1.2.3"]  # one public, one internal

    fetcher = PageFetcher(transport=httpx.MockTransport(_never), resolver=resolver)
    with pytest.raises(BlockedDestinationError):
        await fetcher.fetch("https://sneaky.example/page")


async def test_redirects_to_internal_addresses_are_refused() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "169.254.169.254":
            raise AssertionError("followed a redirect to the metadata service")
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/"})

    fetcher = PageFetcher(transport=httpx.MockTransport(handler), resolver=public)
    with pytest.raises(BlockedDestinationError):
        await fetcher.fetch("https://example.com/go")


async def test_public_redirects_are_followed_and_recorded() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "/new"})
        return httpx.Response(200, text=HTML, headers={"content-type": "text/html"})

    fetcher = PageFetcher(transport=httpx.MockTransport(handler), resolver=public)
    page = await fetcher.fetch("https://example.com/old")
    assert page.final_url == "https://example.com/new"


async def test_responses_are_capped_while_streaming() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text="a " * MAX_BYTES, headers={"content-type": "text/plain"})

    fetcher = PageFetcher(transport=httpx.MockTransport(handler), resolver=public)
    page = await fetcher.fetch("https://example.com/huge")
    assert len(page.full_text) <= MAX_BYTES
