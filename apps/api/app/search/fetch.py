import asyncio
import hashlib
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
import lxml.html
import trafilatura
from lxml import etree
from pydantic import BaseModel

USER_AGENT = "PreuveResearchBot/0.1 (+https://github.com/Vishwas721/Preuve)"
MAX_BYTES = 5_000_000  # read at most this much of a response (streamed, then cut)
MAX_REDIRECTS = 5
ALLOWED_PORTS = {None, 80, 443}

Resolver = Callable[[str], Awaitable[list[str]]]


async def system_resolver(host: str) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return sorted({info[4][0] for info in infos})


class FetchError(Exception):
    """Page couldn't be fetched (network, status, robots.txt, or content type)."""


class BlockedDestinationError(FetchError):
    """The URL points at a non-public address (SSRF guard, Phase 5C)."""


def _public(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%")[0])  # drop an IPv6 zone id
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


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
        resolver: Resolver = system_resolver,
    ) -> None:
        self.respect_robots = respect_robots
        self._resolve = resolver
        # Redirects are followed by hand so every hop's destination is checked (SSRF).
        self._client = httpx.AsyncClient(
            timeout=timeout_s,
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT},
            transport=transport,
        )
        self._robots: dict[str, RobotFileParser | None] = {}

    async def _check(self, url: str) -> None:
        """Only public web servers: http(s) on the default ports, and every address the host
        resolves to must be globally routable (no loopback, private, link-local - which covers
        cloud metadata at 169.254.169.254 - CGNAT, multicast or reserved ranges).

        The host is resolved again when connecting, so a DNS answer that changes in between
        (rebinding) isn't covered; the window is small and the result is only text matching.
        """
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https"):
            raise FetchError(f"Unsupported URL scheme: {url}")
        try:
            port = parts.port
        except ValueError as exc:
            raise BlockedDestinationError(f"Invalid port in {url}") from exc
        if port not in ALLOWED_PORTS:
            raise BlockedDestinationError(f"Only ports 80 and 443 are fetched: {url}")
        host = (parts.hostname or "").rstrip(".")
        if not host:
            raise FetchError(f"No host in {url}")
        try:
            addresses = [str(ipaddress.ip_address(host))]
        except ValueError:
            try:
                addresses = await self._resolve(host)
            except OSError as exc:
                raise FetchError(f"Cannot resolve {host}: {exc}") from exc
        if not addresses or not all(_public(a) for a in addresses):
            raise BlockedDestinationError(f"Refusing a non-public address for {host}")

    async def _get(self, url: str) -> tuple[httpx.Response, str, str]:
        """GET with checked redirects and a size cap. Returns (response, final url, body)."""
        for _ in range(MAX_REDIRECTS + 1):
            await self._check(url)
            async with self._client.stream("GET", url) as resp:
                if resp.is_redirect and resp.headers.get("location"):
                    url = urljoin(url, resp.headers["location"])
                    continue
                chunks, size = [], 0
                async for chunk in resp.aiter_bytes():
                    chunks.append(chunk)
                    size += len(chunk)
                    if size >= MAX_BYTES:
                        break
                raw = b"".join(chunks)[:MAX_BYTES]
                body = raw.decode(resp.encoding or "utf-8", errors="replace")
                return resp, url, body
        raise FetchError(f"Too many redirects for {url}")

    async def _allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            parser: RobotFileParser | None = RobotFileParser()
            try:
                resp, _, body = await self._get(f"{origin}/robots.txt")
            except BlockedDestinationError:
                raise
            except (httpx.HTTPError, FetchError):
                parser = None  # unreachable robots.txt -> treat as no restrictions
            else:
                if resp.status_code in (401, 403):
                    parser.disallow_all = True
                elif resp.status_code >= 400:
                    parser = None
                else:
                    parser.parse(body.splitlines())
            self._robots[origin] = parser
        parser = self._robots[origin]
        return parser is None or parser.can_fetch(USER_AGENT, url)

    async def fetch(self, url: str) -> FetchedPage:
        await self._check(url)
        if self.respect_robots and not await self._allowed(url):
            raise FetchError(f"Disallowed by robots.txt: {url}")
        try:
            resp, final_url, body = await self._get(url)
        except httpx.HTTPError as exc:
            raise FetchError(f"Fetch failed for {url}: {type(exc).__name__}: {exc}") from exc
        if resp.status_code >= 400:
            raise FetchError(f"HTTP {resp.status_code} for {url}")
        content_type = resp.headers.get("content-type", "")
        if "html" not in content_type and "text" not in content_type:
            raise FetchError(f"Unsupported content type '{content_type}' for {url}")

        if "html" in content_type:
            text, title, full_text = await asyncio.to_thread(_extract, body)
        else:  # plain text: nothing to extract
            text, title, full_text = body, None, body
        return FetchedPage(
            url=url,
            final_url=final_url,
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
