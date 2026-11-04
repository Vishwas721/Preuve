# Phase 5D — Ops & deploy

- **Status:** Not started (draft)
- **Goal:** Run Preuve in production for $0, deploy it reproducibly, and be able to recover it.

## Scope (draft)

- **Production images:** API (also runs the arq worker and migrations), web (Next.js
  standalone). Multi-stage, non-root.
- **Production Compose stack:** api, worker, web, postgres, redis, searxng; Ollama on the host
  (or a container); no Mailpit/GreenMail.
- **Public access:** Cloudflare Tunnel (free) for HTTPS on the web app and API, so unsubscribe
  links work for real recipients (`PUBLIC_API_URL`).
- **CI:** build and push images (GHCR), then a deploy smoke test (stack up, migrations, health).
  Deploy = a script that pulls, migrates and restarts.
- **Backups:** scheduled `pg_dump` with rotation; a restore is tested.
- **Logging and errors:** structured logs; error tracking with a free option (self-hosted or
  free tier) — to decide.
- **Health checks** for every service.
- **Legal checklist** before scaling outreach (CAN-SPAM / GDPR / PECR) — a checklist, not legal
  advice.

## Acceptance criteria (draft)

- [ ] Production deploy works from CI with migrations.
- [ ] Backups are verified by a restore.
- [ ] Unsubscribe links work from the public URL.
