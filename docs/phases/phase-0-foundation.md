# Phase 0 — Foundation

- **Status:** Done (2026-10-06, updated 2026-11-01)
- **Goal:** A working skeleton every later phase builds on: infra, API, DB, worker queue, hybrid
  LLM layer, search layer, web shell, CI and docs.
- **PRD refs:** §29–§35 (architecture, async work, database, AI layer, guardrails)

## Scope (delivered)

- **Monorepo:** `apps/api` (FastAPI), `apps/web` (Next.js), `infra/`, `docs/`.
- **Infra (Docker):** Postgres 16 on host port **5435**, Redis 7 on **6381**, SearXNG on **8888**.
  Ollama runs on the host (`11434`).
- **API:** settings from `.env`, `/health` reporting each dependency, ideas CRUD, single-user
  `get_current_user` seam (replaced in Phase 5).
- **DB:** async SQLAlchemy, Alembic, naming conventions, uuid PKs, timestamps. Tables: `users`,
  `ideas`.
- **Worker:** arq on Redis, with a `ping` job proving the round trip.
- **LLM layer (`app/llm/`):**
  - `OllamaProvider`. Default `qwen2.5:7b`, the benchmark winner (see ADR 0002).
  - `GeminiProvider` with a fallback chain: `3.8-flash → 3.6-flash → 2.5-flash`, per-model
    cooldown, SDK retries disabled.
  - `FakeProvider` for tests.
  - `LLMRouter`: picks a provider per `TaskType`, validates output, retries, escalates local →
    Gemini, and downgrades Gemini → local only when Gemini is unavailable.
  - Guardrails: the `Claim` schema (a fact requires evidence ids), `verify_citations`,
    `EVIDENCE_RULES`.
- **Search (`app/search/`):** `SearXNGProvider`, plus a `PageFetcher` that honours robots.txt,
  extracts text with trafilatura and records provenance.
- **Web:** dashboard showing system health and the ideas list. Typed client in `src/lib/api.ts`.
- **Tooling:** ruff, pytest (42 tests, hermetic), GitHub Actions CI for api and web.
- **Scripts:** `app.scripts.llm_smoke` (live provider check), `app.scripts.llm_bench`
  (local model benchmark).

## Out of scope

Any product feature beyond storing an idea. Those start in Phase 1A.

## Data model

| Table | Purpose |
|---|---|
| `users` | Single dev user for now |
| `ideas` | Idea + optional context (PRD §8), `state` = PRD §25 validation state |

## API

`GET /health`, `GET/POST /ideas`, `GET/PATCH/DELETE /ideas/{id}`

## Acceptance criteria

- [x] `docker compose up` brings up Postgres, Redis and SearXNG healthy.
- [x] `GET /health` reports database, redis, searxng, ollama and gemini_configured.
- [x] Ideas CRUD round-trips through Postgres.
- [x] The router validates output and escalates local → Gemini on failure (tested with fakes).
- [x] The Gemini chain falls back model to model and cools down failing models (tested).
- [x] The claim guardrail rejects facts without evidence ids, and unknown ids.
- [x] The web dashboard shows API health and the ideas list.
- [x] CI is green (ruff, pytest, web lint + typecheck + build).

## Notes carried forward

- `qwen2.5:7b` scored 18/22 on the benchmark (llama3.1:8b 16, llama3:8b 14). Every miss came
  from an under-specified extraction prompt, so **prompts must define every label and field**.
- Reddit disallows crawlers in robots.txt, so the fetcher skips it. Decide in Phase 1B whether
  to use Reddit's official API.
- On 2026-11-01, `gemini-3.8-flash` was timing out (504) while 3.6 and 2.5 answered in 1–2s. The
  cooldown handles this; reorder `GEMINI_MODELS` if it persists.
- On Windows, use `127.0.0.1`, not `localhost`: Docker's IPv6 forwarding times out.
