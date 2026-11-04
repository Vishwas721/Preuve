# Phase 5A — Auth & workspaces

- **Status:** Done (2026-11-04)
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

- [x] Users only see their own workspace's data (every route tested at the API level).
      *(`test_tenancy` walks the OpenAPI schema: all 60+ `/ideas/{id}/…` routes return 404 to a
      user of another workspace, reports by id too, and every non-public route returns 401
      signed out; the public set is pinned to 9 paths.)*
- [x] Existing data survives: the migration moves it into the owner's workspace and first-run
      setup claims it (tested; rehearsed on a copy with upgrade/downgrade/upgrade, then applied
      to the real database: both cases in "Founder's workspace").
- [x] Passwords are argon2-hashed; sessions are httpOnly cookies stored only as hashes, expire,
      and end on logout or password change (tested).
- [x] Repeated failed logins are throttled; errors don't reveal whether an email exists (tested).
- [x] Cookie requests from a foreign origin are refused (tested; bearer requests exempt).
- [x] Invites: join by link, roles enforced (members can't manage the workspace), removal ends
      access immediately (tested; live too).
- [x] Suppressions block globally but are listed per workspace (tested).
- [x] The research CLI works with an API token (tested; live: `context` on the real case, and
      `create` + delete of a throwaway idea through the token).
- [x] Web lint, typecheck and build pass; setup, login, invite, switching and settings checked
      in a real browser.

## Verification (2026-11-04)

- API: ruff clean; **297 tests** pass (auth 13, tenancy 4, CLI 4, plus every earlier API test
  now running through a real signed-in session instead of a dependency override). Migrations
  run on an empty database and `alembic check` is clean.
- Web: lint, typecheck and production build pass.
- Live run (Playwright in real Chrome, real database, the web app proxying `/api`):
  - a fresh visit redirects to `/setup`; the owner account claimed the existing data (both
    cases on the board, in "Founder's workspace");
  - Settings → invite → one-time link → a second browser signed up through it and saw both
    cases; the used link then showed "This link doesn't work";
  - an API token was created (shown once) and used by the research CLI against the live API;
  - removing the member: their next request to the case got "Idea not found", and their board
    showed their own (empty) workspace;
  - signing out sent `/ideas/new` to `/login?next=%2Fideas%2Fnew`; a wrong password showed
    "Wrong email or password."; signing in returned to `/ideas/new`;
  - 0 px horizontal overflow at 390 px (login, invite, settings, board; dark); no console errors.
  Afterwards the test accounts, sessions, token and invitation were removed and the owner
  account was returned to *unclaimed*, so first-run setup is still yours to do. The pre-5A
  database dump is kept in the session scratchpad.
- Fixed because of the live run:
  - the browser still called the API cross-site (`NEXT_PUBLIC_API_URL=http://127.0.0.1:8000` in
    `.env` / `apps/web/.env.local`), so the session cookie was never sent back after setup.
    The client now always calls `/api` same-origin and ignores that variable;
  - the research CLI printed `\u2192` for "→" on the Windows console; messages are ASCII now.
- Found while building: the instance-level routes (`/suppressions`, `/outreach/settings`,
  `/outreach/inbox…`) had no auth check at all (they relied on the single-user seam). Every
  router is now private by default in `main.py`, with an explicit public list.

## Decisions (2026-11-04)

See the overview: in-house auth, invite-only, global suppression with scoped view.
Also: 404 for other workspaces' ideas; tokens bound to one workspace; no email sending in 5A.

## Notes

- The tests' `client` fixture signs in a real user (no dependency override of auth), so every
  existing API test now exercises the session path.
- Worker jobs act on ids they were given and don't need a user.
- Restart the arq worker after pulling.
- **Dev setup changed:** the web app reaches the API through its own `/api` proxy
  (`next.config.ts`, `PREUVE_API_INTERNAL_URL`, default `http://127.0.0.1:8000`). Restart
  `pnpm dev` after pulling (rewrites load at start). `NEXT_PUBLIC_API_URL` is no longer used and
  can be removed from `.env` and `apps/web/.env.local`.
- First visit after pulling: `/setup` creates the owner account and keeps every existing case.
- The research CLI needs `PREUVE_API_TOKEN` (Settings → API tokens, in the idea's workspace).
- Carried to 5C: password reset by email, API-wide rate limiting, a review of the Origin-based
  CSRF check, session listing/revocation per device.
- Carried to 5D: `PREUVE_API_INTERNAL_URL` is read when Next builds/starts; the production web
  image must set it to the API container's address.
- The instance has one SMTP/IMAP mailbox shared by all workspaces; replies are matched to the
  right idea by message id, so they land in the right workspace.
