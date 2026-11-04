# Phase 5C — Security

- **Status:** Not started (draft)
- **Goal:** Review and harden the attack surface before Preuve is reachable from the internet.
- **PRD refs:** §36 Outreach safety, §37

## Scope (draft)

- **Rate limiting** on the API (per session/token and per IP), stricter on auth and on
  LLM-triggering endpoints.
- **CSRF and CORS review** of the 5A design (Origin check, SameSite cookies, credentials).
- **Secrets:** no defaults in production (refuse to start with the dev `OUTREACH_SECRET`),
  `.env` handling, rotating the outreach secret and API tokens.
- **Dependency scanning:** `pip-audit` and `pnpm audit` in CI; Dependabot.
- **Security headers** on the web app and the public unsubscribe pages.
- **Password reset** (needs a way to reach users; decide email vs owner reset).
- **Security review** of auth, outreach (header injection, unsubscribe tokens, sending limits),
  SSRF in the page fetcher, prompt injection from fetched pages and replies, file/report
  rendering. Findings recorded and fixed.

## Acceptance criteria (draft)

- [ ] A security review has been done and its findings addressed.
- [ ] Dependency scans run in CI with no known high-severity issues.
- [ ] Rate limits are enforced (tested).
