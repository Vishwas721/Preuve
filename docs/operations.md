# Running Preuve in production

The production stack runs on one machine with Docker (Phase 5D). Everything here is free.

## First deploy

```bash
cp infra/.env.prod.example infra/.env.prod
# fill POSTGRES_PASSWORD, OUTREACH_SECRET and SEARXNG_SECRET with:
python -c "import secrets; print(secrets.token_urlsafe(32))"

infra/scripts/deploy.sh            # pulls the latest CI images from GHCR
# or: infra/scripts/deploy.sh --build   (build from this checkout; then set
#     PREUVE_API_IMAGE=preuve-api, PREUVE_WEB_IMAGE=preuve-web, PREUVE_TAG=local in .env.prod)
```

Open `http://localhost:3100` and do first-run setup (`/setup`). On Windows run the scripts from
Git Bash.

| Service | What it does |
|---|---|
| web | The app, on `127.0.0.1:3100`. Proxies the API at `/api`. |
| api, worker | The API and background jobs (same image). Not published to the host. |
| migrate | Runs `alembic upgrade head` before api/worker start. |
| postgres, redis, searxng | Internal only. |
| backup | Daily compressed dump into `BACKUP_DIR`, 14 days kept. |
| cloudflared | Off. Public HTTPS later (below). |

The local model runs on the host: Ollama must be running there (`OLLAMA_URL` reaches it as
`host.docker.internal`).

## Everyday use (Windows)

`preuve.cmd` at the repo root wraps all of this: `preuve` (start, waits until healthy, opens
the browser), `preuve stop`, `preuve status`, `preuve logs`, `preuve update` (runs `deploy.sh`),
`preuve backup`. It starts Docker Desktop and Ollama if they aren't running.

## Updating

```bash
git pull && infra/scripts/deploy.sh               # latest images built and tested by CI
infra/scripts/deploy.sh --tag <commit sha>        # a specific build (also how to roll back)
```

`deploy.sh` runs migrations before starting the new version and waits for health checks.
Take a backup first if the update includes migrations (`infra/scripts/backup.sh`).

## Backups

- Automatic: daily at `BACKUP_HOUR` (UTC), plus one when the stack first starts.
  Files: `BACKUP_DIR/preuve-<UTC time>.sql.gz`. Point `BACKUP_DIR` at a folder your cloud drive
  syncs to keep a copy off this machine.
- Now: `infra/scripts/backup.sh`.
- Check one restores: `infra/scripts/verify-backup.sh [file]` (restores into a scratch database
  and compares every table's row count with the live one; touches nothing live).
- Restore: `infra/scripts/restore.sh <file>` (takes a safety backup first, asks to confirm,
  stops the app, restores, migrates, restarts).

## Logs and errors

```bash
docker compose -p preuve-prod --env-file infra/.env.prod -f infra/docker-compose.prod.yml logs -f api worker
```

Logs are JSON lines with a `request_id` (also sent back as `X-Request-ID`, handy for bug
reports). Query strings are never logged. Docker keeps 5 × 10 MB per service.
Set `SENTRY_DSN` to send errors to Sentry's free tier (request data and personal data are
stripped); empty means nothing leaves the machine.

## Going public (later)

1. Put a domain on a free Cloudflare account and create a tunnel pointing at `http://web:3000`.
2. In `infra/.env.prod`: `CLOUDFLARE_TUNNEL_TOKEN=…` and `PUBLIC_WEB_URL=https://your.domain`
   (sign-in origin checks and unsubscribe links use it).
3. `docker compose … --profile tunnel up -d`.

Before sending real outreach, go through the [legal checklist](legal-checklist.md).

## Health

`/api/health` (through the web app) reports the database, Redis, SearXNG, Ollama and whether a
Gemini key is set. Every container has a Docker health check; `docker compose … ps` shows them.
