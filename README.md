# Preuve

Evidence-driven customer validation for startup ideas.

> Don't validate an idea by asking people whether they like it. Validate it by finding
> people who experience the problem and observing their behavior, responses,
> commitments, and willingness to pay.

- Product spec: [`docs/PRD.md`](docs/PRD.md)
- Architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/adr/`](docs/adr/)
- Build phases: [`docs/ROADMAP.md`](docs/ROADMAP.md)

## Stack

| Part | Tech |
|---|---|
| API | Python 3.11, FastAPI, SQLAlchemy 2 (async), Alembic, arq |
| Web | Next.js (App Router), TypeScript, Tailwind |
| Data | PostgreSQL 16, Redis 7 |
| Search | Self-hosted SearXNG |
| LLM | Hybrid: local Ollama (light tasks) + Gemini free tier (synthesis) |

## Prerequisites

- Docker Desktop
- Python 3.11 + [uv](https://docs.astral.sh/uv/)
- Node 22 + pnpm
- [Ollama](https://ollama.com) with a model pulled: `ollama pull llama3:8b`
- Optional: a Gemini API key from Google AI Studio

## Setup

```bash
# 1. Config
cp .env.example .env                          # set SEARXNG_SECRET, GEMINI_API_KEY
cp apps/web/.env.example apps/web/.env.local

# 2. Infra: Postgres (host port 5433), Redis (6379), SearXNG (8888)
docker compose --env-file .env -f infra/docker-compose.yml up -d

# 3. API
cd apps/api
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload          # http://127.0.0.1:8000  (docs at /docs)

# 4. Worker (separate terminal, apps/api)
uv run arq app.workers.settings.WorkerSettings

# 5. Web (separate terminal)
cd apps/web
pnpm install
pnpm dev                                      # http://localhost:3000
```

> Environment variables already set in your OS (e.g. `GEMINI_API_KEY`) take precedence over
> `.env`. Use `127.0.0.1` rather than `localhost` for service URLs on Windows (Docker IPv6
> forwarding can time out).

## Checks

```bash
cd apps/api
uv run ruff check . && uv run ruff format --check .
uv run pytest                                 # uses a preuve_test database; no LLM/network needed
uv run python -m app.scripts.llm_smoke        # live check of Ollama + Gemini

cd apps/web
pnpm lint && pnpm typecheck && pnpm build
```

## Repo layout

```
apps/api     FastAPI app (modules/, llm/, search/, workers/, alembic/)
apps/web     Next.js dashboard
infra/       docker compose + SearXNG config
docs/        PRD, architecture, ADRs, roadmap
```
