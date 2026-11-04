# Preuve — Architecture

## Overview

```
                 apps/web  (Next.js, TypeScript)
                        │  HTTP/JSON
                        ▼
                 apps/api  (FastAPI, modular monolith)
       ┌────────────┬───┴─────────┬──────────────┐
   modules/*      llm/          search/       workers/ (arq)
   (domain)    (hybrid router) (SearXNG +       │
       │          │    │        page fetch)     │
       ▼          ▼    ▼            │           ▼
  PostgreSQL   Ollama Gemini     SearXNG      Redis (queue)
  (Docker)     (host) (free API) (Docker)     (Docker)
```

- **Modular monolith.** One FastAPI process plus one worker process sharing the same code. Each PRD
  "service" (§30) is a package under `app/modules/` with its own `models.py`, `schemas.py`,
  `service.py`, `router.py`. Modules talk through service functions, never through each other's
  tables directly. They can be split into services later if ever needed.
- **Async everywhere.** SQLAlchemy 2 async (`asyncpg`), `httpx` async clients, `arq` async workers.
- **Long work runs in workers.** Anything that searches, fetches pages, or makes multiple LLM calls
  is enqueued as an arq job; HTTP handlers only create a run record and return its id (PRD §31).

## Runtime (development)

| Component | Where | Port |
|---|---|---|
| PostgreSQL 16 | Docker (`infra/docker-compose.yml`) | 5435 (host) |
| Redis 7 | Docker | 6381 (host) |
| SearXNG | Docker | 8888 |
| Ollama (`qwen2.5:7b`) | Host | 11434 |
| API (uvicorn) | Host, `apps/api` | 8000 |
| Worker (arq) | Host, `apps/api` | — |
| Web (Next.js) | Host, `apps/web` | 3000 |

## Hybrid LLM layer (`app/llm/`)

No paid APIs. Two real providers behind one interface:

- **OllamaProvider** — local model (default `qwen2.5:7b`, set by `OLLAMA_MODEL`). Uses Ollama's
  `/api/chat` with `format=<JSON schema>` for structured output. Good for single-document,
  short-context tasks.
- **GeminiProvider** — Gemini free tier via `google-genai`, with a **model fallback chain**
  (`GEMINI_MODELS`, default `gemini-3.8-flash → gemini-3.6-flash → gemini-2.5-flash`). A model that
  returns 429 / 5xx / times out (`GEMINI_TIMEOUT_S`) is skipped for `GEMINI_COOLDOWN_S`; invalid
  output moves to the next model without a cooldown. SDK retries are disabled. Used for multi-source
  synthesis and long-context reasoning. Free-tier data may be used by Google to improve models —
  don't send private data (e.g. prospect email bodies) there without the user opting in.
- **FakeProvider** — deterministic, for tests/CI.

The **router** maps each `TaskType` to a provider:

| Task | Default provider | Why |
|---|---|---|
| `classify_evidence`, `extract_fields`, `classify_response`, `summarize_short`, `draft_outreach` | local | single short input, schema-constrained |
| `analyze_idea`, `generate_icps`, `synthesize_evidence`, `analyze_competitors`, `validation_report` | gemini | multi-source reasoning, long context, high hallucination risk on 8B |

Every structured call is validated against a Pydantic schema. On invalid output the router retries,
then **escalates local → Gemini**. Routes are overridable via `LLM_ROUTE_OVERRIDES` in config.

## Evidence guardrails

Enforced in code, not just prompts (PRD §12, §35):

- Every AI claim is a `Claim{statement, kind: fact | inference | assumption, evidence_ids}`.
- A `fact` **must** reference at least one evidence id; otherwise validation fails.
- Evidence records always carry provenance: source URL, fetched-at time, extracted quote.
- When nothing is found the system stores/returns "No evidence found" — never a generic statement.

## Research (ADR 0004)

- **Claude Code is the research analyst.** The `/research-idea` project skill runs a fixed,
  versioned method and writes a **research pack**: JSON matching a schema owned by the API, plus
  a readable report.
- **Preuve verifies.** It imports the pack, fetches every cited URL itself, checks the verbatim
  quote is on the page, and stores evidence as `verified` or `unverifiable`. Items whose quote
  isn't on the page are rejected.
- Packs (schema 1.1) also carry competitors and alternatives plus a "how it's solved today"
  summary. A competitor is stored only if its cited evidence survives verification, and
  re-imports merge by normalized name without overwriting user edits.
- Packs (schema 1.2) also carry companies and contacts. A contact is stored only if a
  **verified** quote contains the person's name, and an email only if it is printed on the
  fetched page. Lead scores (PRD §16) are computed in code (`prospects/scoring.py`) from stored
  evidence only, with a versioned inputs hash for reproducibility.
- Local and Gemini models keep the high-volume, single-input tasks: classification, extraction,
  drafting, reply analysis.

## Search (`app/search/`)

- `PageFetcher` downloads a URL with a timeout and an identifying user agent, respects
  `robots.txt`, and extracts readable text, keeping the URL and fetch time for provenance. It
  is the basis of research verification.
- `SearchProvider` / `SearXNGProvider` (free, keyless) is kept for an optional automated research
  source later; Phase 1B doesn't use it.

## Data

- PostgreSQL, uuid primary keys, `created_at`/`updated_at` on every table.
- Schema is migrated with Alembic. **Each roadmap phase adds only the tables it uses.**
- Personal data is minimized (PRD §37): store only professional, publicly available contact info,
  always with its source.

## Auth

Since Phase 5A (see `docs/phases/phase-5a-auth-workspaces.md`):

- Email + password accounts (argon2id). Browsers hold a session cookie (`httpOnly`,
  `SameSite=Lax`); scripts use personal API tokens (`Authorization: Bearer prv_…`). Only hashes of
  either are stored.
- Ideas belong to a **workspace**; members (owner / member) see everything in it.
  `app.core.deps.get_principal` resolves the caller and their active workspace;
  `ideas.deps.get_owned_idea` returns 404 for other workspaces' ideas.
- Every router is private by default (`app/main.py`); public routes are an explicit list
  (health, unsubscribe, sign-in/setup, invitation links).
- The web app calls the API same-origin at `/api` (a Next rewrite), so the cookie is
  first-party; cookie requests that change state must come from an allowed origin (CSRF).
