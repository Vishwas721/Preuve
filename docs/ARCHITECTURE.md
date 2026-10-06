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
| PostgreSQL 16 | Docker (`infra/docker-compose.yml`) | 5432 |
| Redis 7 | Docker | 6379 |
| SearXNG | Docker | 8888 |
| Ollama (`llama3:8b`) | Host | 11434 |
| API (uvicorn) | Host, `apps/api` | 8000 |
| Worker (arq) | Host, `apps/api` | — |
| Web (Next.js) | Host, `apps/web` | 3000 |

## Hybrid LLM layer (`app/llm/`)

No paid APIs. Two real providers behind one interface:

- **OllamaProvider** — local model (default `llama3:8b`, set by `OLLAMA_MODEL`). Uses Ollama's
  `/api/chat` with `format=<JSON schema>` for structured output. Good for single-document,
  short-context tasks.
- **GeminiProvider** — Gemini free tier via `google-genai` (`GEMINI_MODEL`). Used for multi-source
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

## Search (`app/search/`)

- `SearchProvider` interface; `SearXNGProvider` queries the local SearXNG JSON API (free, no key).
- `fetch_page()` downloads a URL with a timeout and identifying user agent, respects `robots.txt`,
  and extracts readable text. Results keep URL + fetch timestamp for provenance.

## Data

- PostgreSQL, uuid primary keys, `created_at`/`updated_at` on every table.
- Schema is migrated with Alembic. **Each roadmap phase adds only the tables it uses.**
- Personal data is minimized (PRD §37): store only professional, publicly available contact info,
  always with its source.

## Auth

Phase 0–4 run single-user: a seeded dev user is resolved by a `get_current_user` dependency.
Real auth and teams arrive in Phase 5; the dependency is the single seam to replace.
