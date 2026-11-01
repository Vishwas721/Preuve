"""Verbatim-quote matching (Phase 1B decision).

A quote matches when, after normalization, it appears exactly in the page text. An ellipsis
("…", "...", "[...]", "[…]") splits a quote into fragments that must all appear, in order.
"""

import re
import unicodedata
from dataclasses import dataclass

MIN_FRAGMENT_CHARS = 8

_ELLIPSIS = re.compile(r"\[\s*(?:\.\.\.|…)\s*\]|\.{3,}|…")
_ZERO_WIDTH = re.compile("[​‌‍⁠﻿­]")
_WS = re.compile(r"\s+")
_TRANSLATE = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "‚": "'",
        "‛": "'",
        "′": "'",
        "“": '"',
        "”": '"',
        "„": '"',
        "‟": '"',
        "″": '"',
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        "―": "-",
        "−": "-",
    }
)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = _ZERO_WIDTH.sub("", text).translate(_TRANSLATE).lower()
    return _WS.sub(" ", text).strip()


def fragments(quote: str) -> list[str]:
    """Normalized fragments of a quote, split on ellipses."""
    parts = (normalize(p) for p in _ELLIPSIS.split(quote))
    return [p.strip(" ,;:") for p in parts if p.strip(" ,;:")]


@dataclass(frozen=True)
class MatchResult:
    found: bool
    reason: str = ""


def match_quote(quote: str, page_text: str) -> MatchResult:
    frags = fragments(quote)
    if not frags:
        return MatchResult(False, "quote is empty after normalization")
    short = [f for f in frags if len(f) < MIN_FRAGMENT_CHARS]
    if short:
        return MatchResult(False, f"fragment too short to verify: {short[0]!r}")

    haystack = normalize(page_text)
    pos = 0
    for i, frag in enumerate(frags):
        idx = haystack.find(frag, pos)
        if idx == -1:
            where = "" if len(frags) == 1 else f" (fragment {i + 1} of {len(frags)})"
            return MatchResult(False, f"quote not found on page{where}")
        pos = idx + len(frag)
    return MatchResult(True)


def match_any(quote: str, *texts: str | None) -> MatchResult:
    """Try each text in turn (main extract first, then full page); return the first match."""
    last = MatchResult(False, "no page text")
    for text in texts:
        if text:
            last = match_quote(quote, text)
            if last.found:
                return last
    return last


def quote_key(quote: str) -> str:
    """Stable key for deduplicating the same quote across imports."""
    return " … ".join(fragments(quote))
