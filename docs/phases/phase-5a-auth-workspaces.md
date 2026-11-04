# Phase 5A — Auth & workspaces

- **Status:** In progress (kickoff 2026-11-04)
- **Goal:** Replace the single-user seam with real accounts, and put every idea inside a
  workspace that only its members can see.
- **PRD refs:** §6 (solo founder, 2–5 person team), §37 (minimal personal data), §49

## Scope

### Accounts and sessions

- **Email + password.** Passwords hashed with argon2id (`argon2-cffi`), minimum 10 characters,
  checked against a short list of common passwords. Emails are normalised to lower case.
- **Sessions:** a random 32-byte token in an `httpOnly`, `SameSite=Lax` cookie (`Secure` outside
  development). Only its SHA-256 is stored (`sessions` table), so a database leak doesn't leak
  live sessions. 30-day expiry, sliding (renewed when used, at most once an hour). Logout deletes
  the row; changing the password deletes the user's other sessions.
- **Login throttling:** after 5 failed attempts for an email within 15 minutes, further attempts
  for it are refused for 15 minutes (Redis counter). Error messages never say whether the email
  exists. (API-wide rate limiting is 5C.)
- **CSRF:** cookie-authenticated requests with unsafe methods must carry an `Origin` (or
  `Referer`) that's in `CORS_ORIGINS`; otherwise 403. Bearer-token requests are exempt (no
  ambient credentials). 5C reviews this.

### First run

- `POST /auth/setup` works only while no user has a password. It turns the existing dev user
  (`DEV_USER_EMAIL`, who owns all current data) into the instance owner with the email, name and
  password given, so nothing is lost. After that it returns 409.
- Open sign-up is **off** (`ALLOW_SIGNUP=false`). New people join through an invite.

### Workspaces, roles, invites

- A **workspace** holds ideas. Roles: **owner** (manage members, invites and the workspace) and
  **member** (everything with ideas). A workspace always has at least one owner.
- Every user has a personal workspace created with their account; they can create more and
  belong to several. The session carries the **active workspace**; `POST /auth/workspace`
  switches it. The idea list and case board show the active workspace's ideas.
- **Invites:** an owner creates an invite (email + role); the API returns a one-time link
  (token hashed in the DB, 7-day expiry). The owner shares it themselves (no email sending in
  5A). Opening it: sign up with that email (even with sign-up off) or, if signed in as that
  email, accept. Owners can revoke pending invites, change roles and remove members; removing
  a member ends their access immediately.

### Tenant isolation

- `ideas.workspace_id` replaces `ideas.owner_id` (which becomes `created_by_id`, nullable,
  `SET NULL`). The migration creates a workspace per existing user and moves their ideas into it.
- `get_owned_idea` checks membership of the idea's workspace; a non-member gets **404** (not 403,
  so idea ids can't be probed). Every idea-scoped route already goes through it.
- Routes outside `/ideas/{id}` are scoped explicitly: portfolio (active workspace), reports
  (the report's idea's workspace), suppressions (see below), outreach settings and inbox status
  (instance-level, signed-in users only).
- **Suppressions:** `suppressions` gets `workspace_id` (nullable for legacy rows, which go to
  the owner's workspace in the migration); the unique key becomes (email, workspace_id).
  Sending checks **any** row for the address (global block). Listing/deleting shows only the
  active workspace's rows; adding an address already blocked elsewhere says so without
  revealing which workspace. Unsubscribes, bounces and opt-out replies record the row in the
  workspace of the message they relate to.
- **A test walks every route** in the app: each `/ideas/{idea_id}/…` route called by a user of
  another workspace returns 404, and non-public routes return 401 without credentials.

### API tokens (research CLI)

- Personal tokens (`prv_` + 32 random bytes; only the hash is stored, plus a short prefix to
  identify it), each bound to one workspace, with a name, last-used time and revoke.
  Sent as `Authorization: Bearer …`. Shown once on creation.
- `app.scripts.research` reads `PREUVE_API_TOKEN`; the `/research-idea` skill doc says how to
  create one.

## Out of scope

Email verification and password reset by email (needs mail to users; noted for 5C — an owner
can re-invite, and the instance owner can reset a password with a CLI command). SSO/OAuth.
Per-workspace SMTP/IMAP mailboxes (the instance has one mailbox; noted as a limitation).
Audit log of member actions.

## Data model

| Table | Key columns |
|---|---|
| `users` (changed) | + `password_hash?`, `is_active`, `last_login_at?` |
| `workspaces` | name, created_by_id? |
| `memberships` | workspace_id, user_id, role (`owner`/`member`); unique (workspace_id, user_id) |
| `invitations` | workspace_id, email, role, token_hash (unique), invited_by_id?, expires_at, accepted_at?, revoked_at? |
| `sessions` | user_id, token_hash (unique), active_workspace_id?, expires_at, last_seen_at, user_agent |
| `api_tokens` | user_id, workspace_id, name, token_prefix, token_hash (unique), last_used_at?, revoked_at? |
| `ideas` (changed) | + `workspace_id` (not null, CASCADE); `owner_id` → `created_by_id` (nullable, SET NULL) |
| `suppressions` (changed) | + `workspace_id?`; unique (email, workspace_id) |

## API

- `GET /auth/status` (setup needed? sign-up allowed? signed in?), `POST /auth/setup`,
  `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` (user, workspaces with roles, active
  workspace), `POST /auth/workspace` (switch), `POST /auth/password`.
- `POST /workspaces`, `PATCH /workspaces/{id}`, `GET /workspaces/{id}/members`,
  `PATCH/DELETE /workspaces/{id}/members/{user_id}`, `GET/POST /workspaces/{id}/invitations`,
  `DELETE /workspaces/{id}/invitations/{inv_id}`.
- `GET /invitations/{token}` (public: workspace name, email, role, valid?),
  `POST /invitations/{token}/accept` (signed in as that email), `POST /invitations/{token}/signup`.
- `GET/POST /auth/tokens`, `DELETE /auth/tokens/{id}`.
- CLI: `uv run python -m app.scripts.users reset-password <email>`.

## UI (Dossier design)

- `/setup` (first run), `/login`, `/invite/[token]`.
- Top bar: workspace switcher and account menu (settings, sign out).
- `/settings`: profile and password; workspace name; members and roles; invites (create, copy
  link, revoke); API tokens (create, shown once, revoke).
- Any 401 from the API sends the browser to `/login` (or `/setup` on a fresh install).

## Acceptance criteria

- [ ] Users only see their own workspace's data (every route tested at the API level).
- [ ] Existing data survives: the migration moves it into the owner's workspace and first-run
      setup claims it (tested, and on the real database).
- [ ] Passwords are argon2-hashed; sessions are httpOnly cookies stored only as hashes, expire,
      and end on logout or password change (tested).
- [ ] Repeated failed logins are throttled; errors don't reveal whether an email exists (tested).
- [ ] Cookie requests from a foreign origin are refused (tested).
- [ ] Invites: join by link, roles enforced (members can't manage the workspace), removal ends
      access immediately (tested).
- [ ] Suppressions block globally but are listed per workspace (tested).
- [ ] The research CLI works with an API token (tested; live import on the real case).
- [ ] Web lint, typecheck and build pass; setup, login, invite, switching and settings checked
      in a real browser.

## Decisions (2026-11-04)

See the overview: in-house auth, invite-only, global suppression with scoped view.
Also: 404 for other workspaces' ideas; tokens bound to one workspace; no email sending in 5A.

## Notes

- The tests' `client` fixture signs in a real user (no dependency override of auth), so every
  existing API test now exercises the session path.
- Worker jobs act on ids they were given and don't need a user.
- Restart the arq worker after pulling.
