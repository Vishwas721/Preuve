# Phase 5D — Ops & deploy

- **Status:** Done (2026-11-05)
- **Goal:** Run Preuve in production on this machine for $0, deploy it reproducibly from CI-built
  images, and be able to recover it.

## Decisions at kickoff (2026-11-05)

- **Local only for now.** The production stack runs on this machine, reachable at
  `http://localhost:3100`. A Cloudflare Tunnel service is included but **off** (a compose
  profile); turning it on later needs a domain on a free Cloudflare account and a tunnel token.
- **Errors:** structured JSON logs (request id on every line, rotated by Docker), plus an
  optional Sentry hook that's off unless `SENTRY_DSN` is set (nothing leaves the machine by
  default).
- **Backups:** a daily compressed `pg_dump` with 14 days of rotation into `BACKUP_DIR`
  (default `./backups`; point it at a cloud-synced folder for an off-machine copy).
- **Registry:** the repo is public, so CI pushes images to GHCR for free.

## Scope

### Images

- **API** (`apps/api/Dockerfile`): Python 3.11 slim, multi-stage with `uv`, dependencies from
  the lockfile only, non-root user, health check. The same image runs the API, the arq worker
  and migrations (different commands).
- **Web** (`apps/web/Dockerfile`): Node 22, pnpm from the lockfile (supply-chain policy intact),
  Next.js `output: "standalone"`, non-root. `PREUVE_API_INTERNAL_URL=http://api:8000` is baked in
  at build time (rewrites are compiled into the build).

### Production stack (`infra/docker-compose.prod.yml`, project `preuve-prod`)

| Service | Notes |
|---|---|
| postgres, redis, searxng | Internal network only, no host ports; named volumes. |
| migrate | One-shot `alembic upgrade head`; api and worker start only after it succeeds. |
| api | Not published to the host: only the web app reaches it (so `TRUST_PROXY_HEADERS=true` is safe and per-IP limits work). |
| worker | arq, including the daily page-text purge. |
| web | Published on `127.0.0.1:${WEB_PORT:-3100}`. The browser reaches the API at `/api`. |
| backup | `pg_dump` daily at `BACKUP_HOUR`, gzip, keeps `BACKUP_KEEP_DAYS` (14). |
| cloudflared | Profile `tunnel`, off by default. |

- Ollama stays on the host (`OLLAMA_URL=http://host.docker.internal:11434`).
- Every service has a health check; every service's logs rotate (10 MB × 5).
- Settings come from `infra/.env.prod` (git-ignored); `infra/.env.prod.example` lists them,
  and the API already refuses to start with dev secrets outside development (5C).
- `PUBLIC_API_URL=http://localhost:3100/api`, so unsubscribe links resolve through the web app's
  proxy (once tunnelled, the public URL replaces it).

### Logging and errors

- `LOG_FORMAT=json`: one JSON object per line (time, level, logger, message, request id,
  method, path, status, duration); the request id is returned as `X-Request-ID`.
- `SENTRY_DSN` (optional): errors from the API and the worker go to Sentry, without request
  bodies, cookies or personal data (`send_default_pii=False`).

### Scripts (`infra/scripts/`, bash; run from Git Bash on Windows)

- `deploy.sh [tag]`: pull images from GHCR (or `--build` locally), run migrations, start the
  stack, wait until healthy, print the URL.
- `backup.sh`: take a backup now. `restore.sh <dump>`: restore a dump (asks for confirmation,
  stops api/worker first).
- `verify-backup.sh`: restore the latest dump into a scratch database and compare row counts
  with the live one (the "backups are verified by a restore" check).

### CI

- Build both images on every push; on `main`, push them to GHCR as `:sha` and `:latest`.
- **Deploy smoke test**: start the production stack from the just-built images with generated
  secrets, wait for health, check migrations are at head, call `/api/health` and an
  unauthenticated route through the web app, take a backup and verify it by a restore.

### Legal checklist

`docs/legal-checklist.md`: CAN-SPAM, GDPR/UK GDPR and PECR points to check before scaling
outreach, mapped to what Preuve already does (identity, unsubscribe, suppression, deletion,
minimisation) and what the operator must still decide. A checklist, not legal advice.

## Out of scope

A public deployment (no domain yet). Managed Postgres/Redis (local volumes instead).
Self-hosted error dashboards. Kubernetes.

## Acceptance criteria

- [x] Production images build in CI and are pushed to GHCR; both run as non-root (uid 10001;
      `ghcr.io/vishwas721/preuve-api` and `preuve-web`, tagged with the commit and `latest`,
      publicly pullable).
- [x] The CI deploy smoke test brings the stack up from those images with migrations applied
      (run 41975973235: health ok, `alembic current` at head, `/login` served, `/api/ideas` 401
      signed out; the pushed images are the ones that were tested).
- [x] The stack runs on this machine via `deploy.sh`, healthy, with the real data migrated in
      (first with local builds, then from the GHCR images; 2 cases and 61 exhibits).
- [x] Backups run on schedule and are verified by a restore (in CI and locally: 35 tables,
      row counts match).
- [x] Unsubscribe links work through the production stack's URL (a real signed link opened at
      `http://localhost:3100/api/unsubscribe/…`, confirmed, address suppressed in the right
      workspace; the form posts back to the same proxied URL).
- [x] Logs are structured JSON with request ids; Sentry is off unless configured (tested).
- [x] The legal checklist exists and is linked from the README.

## Verification (2026-11-05)

- API: ruff clean; **336 tests** pass (observability 6). Web: lint, typecheck and build pass.
- CI (all three jobs green): images built, the production stack deployed with generated secrets,
  smoke checks, `backup.sh` + `verify-backup.sh` OK, images pushed to GHCR.
- Local: `deploy.sh --build`, then the dev data restored with `restore.sh` (safety backup taken
  first), `backup.sh` + `verify-backup.sh` OK, then `deploy.sh` pulling the CI images; every
  service healthy (api, worker, web, postgres, redis, searxng, backup), Ollama on the host
  reachable from the containers; logs are JSON lines; the app loads in Chrome at 1360 px and
  390 px with no overflow and no console errors; `X-Powered-By` hidden.
- Fixed during the build: settings crashed on import inside a container (the repo-root lookup
  assumed the repo layout); Git Bash rewrote container paths in `docker exec` arguments and then
  host paths for `docker compose` (scripts now disable that conversion and pass native paths);
  `restore.sh` pulled from GHCR when the stack used local builds (the local image names now live
  in `.env.prod`); health checks made the HTTP client log every 15 s (now warnings only).

## Notes

- From 5C: `TRUST_PROXY_HEADERS=true` only because the API isn't published; a real
  `OUTREACH_SECRET` is required.
- From 5A: rewrites are compiled at build time, hence the build-time `PREUVE_API_INTERNAL_URL`.
- The dev stack (`infra/docker-compose.yml`) is unchanged and uses different ports, so both can
  exist side by side (memory permitting).
- **Two copies of the data now exist:** the dev database (`infra/docker-compose.yml`, port 5435)
  is untouched; the production stack (`http://localhost:3100`) has a copy restored from it on
  2026-11-05. Use the production one from here on; first-run setup is still to do there.
- `infra/.env.prod` has generated secrets but no `GEMINI_API_KEY` or SMTP/IMAP settings: copy
  them from `.env` if you want those features in production.
- GitHub warns that `actions/checkout@v4`, `setup-node@v4`, `pnpm/action-setup@v4` and
  `astral-sh/setup-uv@v6` run on deprecated Node 20; Dependabot (5C) will propose upgrades.
- Going public later: `docs/operations.md` → "Going public".
