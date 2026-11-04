# Phase 5C — Security

- **Status:** In progress (kickoff 2026-11-04)
- **Goal:** Review and harden the attack surface before Preuve is reachable from the internet.
- **PRD refs:** §36 Outreach safety, §37

## Review (kickoff, 2026-11-04)

| # | Area | Finding | Severity | Plan |
|---|---|---|---|---|
| S1 | Page fetcher | Fetches any URL and follows redirects, with no check of the destination. A research pack (any workspace member or API token can import one) can make the server fetch `127.0.0.1`, `10.x`, `169.254.169.254`… and quote verification then confirms what those pages say (SSRF). | High | Only `http`/`https` on ports 80/443; resolve the host and refuse loopback, private, link-local, CGNAT, multicast, reserved and unspecified addresses; follow redirects by hand (max 5), checking every hop (robots.txt too); cap responses at 5 MB. |
| S2 | Next.js | 16.3.8 has 2 critical + 1 high advisories (fixed in 16.4.1). | Critical | Upgrade `next` and `eslint-config-next`. |
| S3 | Web deps | `zod`, `minimatch`, `deepmerge` advisories come only through `shadcn`, a code-copying CLI wrongly listed as a runtime dependency. | High | Move `shadcn` to devDependencies. |
| S4 | API deps | `certifi`, `opentelemetry-api`, `pyasn1` have fixed versions. | Medium | Upgrade in `uv.lock`. |
| S5 | Secrets | In production the API starts with the dev `OUTREACH_SECRET` (unsubscribe links could be forged). | High (in prod) | Refuse to start outside development with a default or short (< 32 chars) secret. |
| S6 | Abuse | No rate limiting beyond failed logins; LLM- and job-triggering endpoints can be hammered. | Medium | Redis rate limits (below), 429 + `Retry-After`. |
| S7 | Headers | No security headers: the web app can be framed (clickjacking on Settings → erase/invite); no `nosniff`, referrer policy or HSTS. | Medium | Headers on the web app and the API (below). |
| S8 | Request size | No body size limit (a huge pack or reply). | Low | 5 MB limit → 413. |
| S9 | Email headers | CR/LF in a subject or recipient name is refused by Python's email library, but only at send time: one bad message aborts the rest of a campaign send. Header injection itself is not possible. | Low | Collapse line breaks in header fields before building the message. |
| S10 | API docs | `/docs`, `/redoc`, `/openapi.json` are public. | Low | Off outside development. |
| S11 | Password reset | None besides the CLI (deferred from 5A). | — | Instance-owner reset links (below). |
| S12 | Supply chain | No dependency scanning in CI. | — | `pip-audit` and `pnpm audit --prod` in CI (fail on high/critical); Dependabot. |

Reviewed and fine (no change): login timing and generic errors; session/token storage (hashes);
CSRF (Origin check on cookie writes, `SameSite=Lax`, no state-changing GET routes); tenant
isolation (route walk, 5A); unsubscribe tokens (HMAC-SHA256, constant-time compare, GET shows /
POST confirms); the unsubscribe page escapes its HTML; the web app renders no raw HTML
(`dangerouslySetInnerHTML` is unused; reports and replies are rendered as text); outreach
settings expose no credentials; LLM output is only ever data (structured, quotes verified, no
tools), and drafts written from untrusted page text still need human approval before sending.

## Scope

### Rate limits (S6)

Redis fixed windows, keyed per caller (user or API token) or per IP for public routes:

| Group | Limit |
|---|---|
| Any signed-in request | 600 / minute per caller |
| Expensive (LLM or background job): analyze, ICPs, research import, drafts, send, reanalyze reply, guide, extract, report, inbox check | 30 / 10 minutes per caller |
| Public auth: setup, sign-up, login, invitation look-up/sign-up, reset look-up/use | 30 / minute per IP |
| Unsubscribe pages | 60 / minute per IP |

If Redis is unreachable the check is skipped (logged), like the login throttle. The client IP is
the socket address unless `TRUST_PROXY_HEADERS=true` (behind Cloudflare Tunnel, 5D), which uses
`CF-Connecting-IP` / the first `X-Forwarded-For`.

### Security headers (S7)

- **Web:** `Content-Security-Policy: frame-ancestors 'none'; base-uri 'self'; form-action 'self';
  object-src 'none'`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` (camera, microphone,
  geolocation off). (A full script CSP would need nonces through Next; noted for later.)
- **API:** `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy:
  no-referrer`, `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline';
  frame-ancestors 'none'` (the API serves JSON plus the unsubscribe pages),
  `Cache-Control: no-store` on authenticated responses and exports; HSTS outside development.

### Password reset links (S11, agreed at kickoff, narrowed for safety)

- The **instance owner** (the account that ran first-run setup) can create a one-time reset
  link for any user (1 hour, token hashed). Opening it sets a new password and signs that user
  out everywhere. The CLI stays.
- Workspace owners can't create them: a reset link lets its creator sign in as that user, which
  would give a workspace owner the user's *other* workspaces.

### Supply chain (S2–S4, S12)

Upgrades as above; CI runs `uvx pip-audit` and `pnpm audit --prod --audit-level high`;
`.github/dependabot.yml` (uv, npm, GitHub Actions; weekly).

## Out of scope

A full nonce-based script CSP for the web app. Sign-out of other devices / session list (noted).
WAF/bot protection (Cloudflare can add it in 5D). Penetration testing by a third party.

## Data model

| Table | Change |
|---|---|
| `users` | + `is_instance_owner` (set by first-run setup) |
| `password_resets` (new) | user_id, token_hash (unique), created_by_id?, expires_at, used_at? |

## API

- `POST /admin/users/{user_id}/reset-link` (instance owner), `GET /admin/users` (instance
  owner: users and their workspaces, for picking whom to reset).
- `GET /password-reset/{token}` (public: valid? whose email), `POST /password-reset/{token}`
  (public: set the password).

## UI

Settings → **Accounts** (instance owner only): users, "Create reset link" (shown once).
`/reset/[token]`: set a new password.

## Acceptance criteria

- [ ] The fetcher refuses private, loopback, link-local and metadata addresses, including via
      redirects (tested).
- [ ] No high or critical advisories in production dependencies (`pip-audit`, `pnpm audit --prod`);
      both run in CI; Dependabot configured.
- [ ] Production refuses to start with the dev outreach secret (tested).
- [ ] Rate limits return 429 with `Retry-After` (tested).
- [ ] Security headers are set on the web app and the API (tested / checked live).
- [ ] Oversized requests get 413; a bad header field no longer aborts a campaign send (tested).
- [ ] Reset links: only the instance owner can create them; one use, 1 hour; all sessions end
      (tested).
- [ ] Web lint, typecheck and build pass; reset flow and headers checked in a real browser.

## Decisions (2026-11-04)

- Reset links by the instance owner only (the user chose owner-made links; narrowed because a
  workspace owner could otherwise take over a member's account).
- Rate-limit numbers as above; fail open if Redis is down.
- Script CSP deferred; framing, sniffing and referrer protections now.

## Notes

- From 5A: review the Origin-based CSRF check (done above: fine), password reset (S11), API-wide
  rate limiting (S6).
- 5D needs `TRUST_PROXY_HEADERS=true` behind the tunnel and a real `OUTREACH_SECRET`.
