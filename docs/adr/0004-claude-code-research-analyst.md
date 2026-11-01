# ADR 0004 — Claude Code as the research analyst; Preuve verifies

- **Status:** accepted
- **Date:** 2026-11-01
- **Supersedes:** the automated SearXNG research pipeline planned for Phase 1B (ADR 0003 stays
  in force for search and page fetching, which are now used for verification)

## Context

Research quality decides whether Preuve is useful. The original Phase 1B plan had a crawler:
SearXNG search, then fetch, then a local 8B model pulling quotes from each page. Phase 0 and 1A
showed the limits of the free models (narrow reasoning, overloaded Gemini free tier). Claude Code,
which the founder already uses, can search the web, read full pages, follow leads and judge
sources far better, at no extra cost.

The product's core rule still applies: AI output is never evidence by itself (PRD §12, §35).
That includes Claude.

## Decision

- **Research is done in Claude Code** with a project skill, `/research-idea`. It follows a fixed,
  versioned method and writes a structured **research pack**: JSON matching a schema owned by the
  API, plus a readable report.
- **Preuve imports and verifies the pack.** For each evidence item it fetches the URL itself,
  checks that the verbatim quote appears on the page, and stores the item with provenance and a
  verification status. Items whose quote can't be found are rejected. Items whose page can't be
  fetched (robots.txt, paywall, error) are kept but marked **unverifiable**, and are kept
  separate from verified evidence.
- **Local and Gemini models** keep the high-volume, single-input tasks: classification,
  extraction, outreach drafts, reply analysis.
- **The automated crawler is deferred.** It may come back later as an optional source that
  produces the same pack format.

## Consequences

- Research is better at no added cost, but it is **manual**: a person runs the skill. That's fine
  for the founder's own idea portfolio. A multi-user product would need an automated or
  API-based researcher that produces the same pack (revisit in Phase 5).
- Comparable results depend on the skill's fixed method and schema. Both are versioned
  (`method_version`, `schema_version`), and every import records them.
- Claude's mistakes are caught the same way any model's are: quotes are verified against the
  live page, citations are checked against imported evidence ids, and "No evidence found" is a
  valid result.
