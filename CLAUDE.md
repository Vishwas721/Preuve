# CLAUDE.md — Working rules for Preuve

Preuve is an evidence-driven customer-validation engine. Spec: `docs/PRD.md`.
Architecture: `docs/ARCHITECTURE.md`. Build order: `docs/ROADMAP.md`.

## Phase discipline
- Work only on the current roadmap phase. Read its section in `docs/ROADMAP.md` before starting.
- Don't add tables, endpoints or UI belonging to a later phase.
- Finish a phase by checking its acceptance criteria, updating its status in `ROADMAP.md`, and
  stopping for review.

## Commits
- Small, single-purpose commits in Conventional Commit style: `feat(api): …`, `fix(web): …`,
  `docs: …`, `test(api): …`, `chore(infra): …`, `ci: …`.
- Push each commit to `origin/main`.
- Never commit `.env` or secrets.

## Evidence guardrails (non-negotiable)
- Never present AI output as evidence. Every AI claim is a `Claim` with kind
  `fact | inference | assumption`; a `fact` must cite evidence ids (`app/llm/guardrails.py`).
- Evidence always stores source URL, fetched-at time and the verbatim quote.
- Empty results say "No evidence found." — never a generic filler statement.
- Prompts must instruct the model to use only provided sources and to return empty lists when
  unsure.

## Backend conventions (`apps/api`)
- Python 3.11, FastAPI, SQLAlchemy 2 async, Alembic, arq. Managed with `uv`.
- One package per domain under `app/modules/<name>/` with `models.py`, `schemas.py`,
  `service.py`, `router.py`. Cross-module access goes through service functions.
- New models must be imported in `app/db/models.py` so Alembic sees them; generate migrations
  with `uv run alembic revision --autogenerate -m "…"` and review them.
- Multi-step / network-heavy work runs in arq jobs (`app/workers/`), never in a request handler.
- LLM calls go through `app.llm.router.LLMRouter` with a `TaskType`; never call a provider directly
  from domain code.
- Tests use `FakeProvider` and mocked HTTP; tests must not need Ollama, Gemini or the internet.
- Lint/format: `uv run ruff check .` and `uv run ruff format .`; tests: `uv run pytest`.

## Frontend conventions (`apps/web`)
- Next.js App Router, TypeScript strict, Tailwind. pnpm.
- All API calls go through `src/lib/api.ts`.

## Common commands
```bash
docker compose -f infra/docker-compose.yml up -d     # postgres, redis, searxng
cd apps/api && uv sync && uv run alembic upgrade head
uv run uvicorn app.main:app --reload                 # API on :8000
uv run arq app.workers.settings.WorkerSettings       # worker
cd apps/web && pnpm install && pnpm dev              # web on :3000
```
