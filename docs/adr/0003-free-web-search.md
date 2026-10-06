# ADR 0003 — Self-hosted SearXNG for web search

- **Status:** accepted
- **Date:** 2026-10-06

## Context
The research engine needs web search. LLMs don't search on their own, and paid search APIs are out.

## Decision
Run SearXNG (metasearch) in Docker with the JSON output format enabled, behind a `SearchProvider`
interface. Page fetching respects `robots.txt` and records provenance.

## Consequences
- Free and keyless; result quality depends on upstream engines and may be rate limited.
- The interface allows adding another provider later without touching research code.
