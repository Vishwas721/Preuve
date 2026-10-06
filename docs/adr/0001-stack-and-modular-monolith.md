# ADR 0001 — Stack and modular monolith

- **Status:** accepted
- **Date:** 2026-10-06

## Context
Preuve is built by a solo founder. The PRD sketches a set of services (§29–§30) but the team size
and early product stage don't justify distributed services.

## Decision
- Backend: Python 3.11, FastAPI, SQLAlchemy 2 (async), Alembic, arq on Redis.
- Frontend: Next.js (App Router), TypeScript, Tailwind.
- Database: PostgreSQL 16.
- Dev infra via Docker Compose (Postgres, Redis, SearXNG); app processes run on the host.
- One deployable API + one worker process; PRD services become packages under `app/modules/`.

## Consequences
- Simple local development and deployment; one codebase to test.
- Module boundaries must be respected by convention (service functions, no cross-module table
  access) so a later split stays possible.
