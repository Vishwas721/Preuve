import asyncio
import hashlib
from datetime import UTC, datetime
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
import lxml.html
import trafilatura
from lxml import etree
from pydantic import BaseModel

USER_AGENT = "PreuveResearchBot/0.1 (+https://github.com/Vishwas721/Preuve)"
MAX_BYTES = 3_000_000


class FetchError(Exception):
    """Page couldn't be fetched (network, status, robots.txt, or content type)."""


class FetchedPage(BaseModel):
    """A fetched page with provenance: where it came from and when."""

    url: str
    final_url: str
    status_code: int
    fetched_at: datetime
    title: str | None
    text: str  # main content (trafilatura)
    full_text: str  # every visible text node; fallback for quote verification
    content_hash: str  # sha256 of full_text


class PageFetcher:
    """Polite page fetcher: identifies itself, honours robots.txt, extracts readable text."""

    def __init__(
        self,
        *,
        timeout_s: float = 20.0,
        respect_robots: bool = True,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.respect_robots = respect_robots
        self._client = httpx.AsyncClient(
            timeout=timeout_s,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
            transport=transport,
        )
        self._robots: dict[str, RobotFileParser | None] = {}

    async def _allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            parser: RobotFileParser | None = RobotFileParser()
            try:
                resp = await self._client.get(f"{origin}/robots.txt")
            except httpx.HTTPError:
                parser = None  # unreachable robots.txt -> treat as no restrictions
            else:
                if resp.status_code in (401, 403):
                    parser.disallow_all = True
                elif resp.status_code >= 400:
                    parser = None
                else:
                    parser.parse(resp.text.splitlines())
            self._robots[origin] = parser
        parser = self._robots[origin]
        return parser is None or parser.can_fetch(USER_AGENT, url)

    async def fetch(self, url: str) -> FetchedPage:
        if urlsplit(url).scheme not in ("http", "https"):
            raise FetchError(f"Unsupported URL scheme: {url}")
        if self.respect_robots and not await self._allowed(url):
            raise FetchError(f"Disallowed by robots.txt: {url}")
        try:
            resp = await self._client.get(url)
        except httpx.HTTPError as exc:
            raise FetchError(f"Fetch failed for {url}: {exc}") from exc
        if resp.status_code >= 400:
            raise FetchError(f"HTTP {resp.status_code} for {url}")
        content_type = resp.headers.get("content-type", "")
        if "html" not in content_type and "text" not in content_type:
            raise FetchError(f"Unsupported content type '{content_type}' for {url}")
        body = resp.text[:MAX_BYTES]

        if "html" in content_type:
            text, title, full_text = await asyncio.to_thread(_extract, body)
        else:  # plain text: nothing to extract
            text, title, full_text = body, None, body
        return FetchedPage(
            url=url,
            final_url=str(resp.url),
            status_code=resp.status_code,
            fetched_at=datetime.now(UTC),
            title=title,
            text=text,
            full_text=full_text,
            content_hash=hashlib.sha256(full_text.encode()).hexdigest(),
        )


def _extract(html: str) -> tuple[str, str | None, str]:
    text = trafilatura.extract(html, include_comments=False, include_tables=True) or ""
    meta = trafilatura.extract_metadata(html)
    return text, (meta.title if meta else None), _visible_text(html)


def _visible_text(html: str) -> str:
    try:
        root = lxml.html.fromstring(html)
    except (etree.ParserError, ValueError):
        return ""
    etree.strip_elements(root, "script", "style", "noscript", "template", with_tail=False)
    return " ".join(t.strip() for t in root.itertext() if t.strip())
