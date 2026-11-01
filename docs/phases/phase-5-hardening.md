# Phase 5 — Hardening

- **Status:** Not started (draft)
- **Goal:** Make Preuve safe to use for more than one person, and deployable.
- **PRD refs:** §6 (teams), §36 Safety, §37 Privacy & compliance, §49 (multi-user teams)

## Scope

- **Auth:** real sign-up and sign-in, replacing the single-user `get_current_user` seam.
  Sessions or JWT; password hashing or an OAuth provider.
- **Teams:** workspaces with members and roles (owner, member). Ideas belong to a workspace.
- **Privacy (PRD §37):**
  - contact deletion and export;
  - a deletion request adds the address to the suppression list;
  - retention rules for fetched page text;
  - a provenance audit (every contact and evidence item has a source).
- **Security:**
  - secrets management;
  - rate limiting on the API;
  - CORS and CSRF review;
  - dependency scanning;
  - a security review of outreach and auth.
- **Ops:**
  - production Docker images;
  - deployment target (to decide);
  - managed Postgres and Redis;
  - backups, logging and error tracking;
  - health checks.
- **Legal checklist** before scaling outreach (CAN-SPAM / GDPR / PECR review).

## Out of scope

Billing. CRM integrations (PRD §49, later).

## Data model (draft)

`workspaces`, `memberships`, auth tables (depending on the approach); `ideas.workspace_id`
replaces `ideas.owner_id` in a migration.

## Acceptance criteria

- [ ] Users only see their own workspace's data (tested at the API level).
- [ ] Deleting a contact removes their personal data and suppresses the address.
- [ ] Production deploy works from CI with migrations; backups are verified by a restore.
- [ ] A security review has been done and its findings addressed.

## Open questions (settle at kickoff)

- Hosting target and budget (free tiers vs a VPS).
- Build auth in-house or use a provider?
