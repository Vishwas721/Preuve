# Phase 5 — Hardening (overview)

- **Status:** In progress — split into 5A–5D at kickoff (2026-11-04)
- **Goal:** Make Preuve safe to use for more than one person, and deployable, for $0.
- **PRD refs:** §6 (teams), §36 Safety, §37 Privacy & compliance, §49 (multi-user teams)

Phase 5 was about four phases of work, so it's split like Phase 1. Each sub-phase has its own
doc and ends with a review stop.

| Sub-phase | Doc | Scope |
|---|---|---|
| 5A — Auth & workspaces | [phase-5a-auth-workspaces.md](phase-5a-auth-workspaces.md) | Sign-in, sessions, workspaces, roles, invites, API tokens, tenant isolation |
| 5B — Privacy | [phase-5b-privacy.md](phase-5b-privacy.md) | Contact export, deletion audit, retention of fetched text, provenance audit |
| 5C — Security | [phase-5c-security.md](phase-5c-security.md) | Rate limiting, CSRF/CORS review, secrets, dependency scanning, security review |
| 5D — Ops & deploy | [phase-5d-ops-deploy.md](phase-5d-ops-deploy.md) | Production images, self-hosted deploy + tunnel, backups, logging, legal checklist |

## Decisions (2026-11-04)

- **Split** into 5A–5D, built in that order (auth first: everything else assumes real users).
- **Hosting:** self-hosted production Docker Compose stack (your machine or any Docker host),
  exposed through a free **Cloudflare Tunnel** for HTTPS and public unsubscribe links. Ollama
  stays local; cost $0. CI builds the images and runs a deploy smoke test; deploying is a
  pull + migrate script. Oracle Cloud Always Free can run the same stack later.
- **Auth:** in-house. Email + password (argon2), server-side sessions in an httpOnly cookie,
  invite-only workspaces, personal API tokens for the research CLI. No external service.
- **Suppressions:** blocking stays global (an opted-out address is never emailed by any
  workspace), but each workspace only sees and manages the entries it created.

## Out of scope

Billing. CRM integrations (PRD §49, later). SSO / OAuth providers.

## Acceptance (whole phase; each sub-phase doc has its own detailed list)

- [x] Users only see their own workspace's data (tested at the API level). — 5A
- [ ] Deleting a contact removes their personal data and suppresses the address. — 5B
- [ ] A security review has been done and its findings addressed. — 5C
- [ ] Production deploy works from CI with migrations; backups are verified by a restore. — 5D
