# Phase 2 — Outreach

- **Status:** In progress (kickoff 2026-11-03)
- **Goal:** Send a small number of honest, research-oriented messages to well-chosen prospects,
  with a human approving every one.
- **PRD refs:** §17 Outreach generation, §18 Human approval gate, §19 Outreach experiment,
  §36 Safety & deliverability, §37 Privacy, §42 Email workspace

## Scope

- **Campaigns.** A campaign belongs to an idea and holds a name, an optional ICP, a research
  purpose (one or two plain sentences, shown to the drafter and in every message), a daily
  limit and a status (`active` / `paused`).
- **Drafting** (`draft_outreach`, local → Gemini fallback), in an arq job. The user picks
  contacts of the idea's prospects; one draft is created per contact (`drafting`), and the job
  fills it in. The model gets only: the hypothesis problem, the campaign purpose, the sender's
  name, the contact's name and role, the company's name and description, and the company's
  verified, non-dismissed evidence (id + quote). Each draft:
  - names the recipient and says why they were selected (`why_selected`, shown to the user);
  - may cite real public evidence, by evidence id; ids are checked with `verify_citations`
    against the evidence it was given, and an unknown id counts as invalid output (retried);
  - states the research purpose and asks one small question;
  - never claims the product exists, never exaggerates.
  If every provider fails, the draft stays empty with `draft_error` set; the user can write it by
  hand. Nothing is filled with a template.
- **Draft checks** (deterministic, shown as warnings, not blockers): mentions of a product /
  demo / sign-up / pricing / "we built"; more than one question mark; a body over 150 words;
  no mention of the recipient's name.
- **Recipient address.** The contact's email if it's printed on a verified page
  (`to_email_source = public_page`); otherwise the user types it on the draft
  (`user_entered`). Approval requires an address.
- **Approval gate:** `drafting → draft`; `draft → approved | rejected`; `rejected → draft`;
  `approved → sent | bounced | blocked`. Editing an approved message returns it to `draft`.
  Approval stores `approved_hash` = SHA-256 of (to, subject, body); the send job refuses any
  message whose current hash differs. Sending an unapproved message is impossible, enforced in
  the service and the job, and tested.
- **Email provider.** `EmailProvider` interface with `SmtpProvider` (stdlib `smtplib` in a
  thread, STARTTLS/SSL) and `FakeEmailProvider` for tests. Credentials only in `.env`. With no
  `SMTP_HOST` set, sending is disabled and says so. Dev points at **Mailpit** (a local mail
  catcher in docker compose: SMTP `1025`, UI `http://localhost:8025`), so nothing leaves the
  machine. Real sends use a Gmail app password (see *Sender setup*).
- **Safety (PRD §36), all re-checked in the job immediately before each send:**
  - approval + unchanged content (`approved_hash`);
  - global suppression list (case-insensitive email) → message becomes `blocked`;
  - per-campaign daily limit (default 10) and a global daily limit across all campaigns
    (`OUTREACH_DAILY_LIMIT`, default 20) → message stays `approved`, reported as deferred;
  - contact frequency: no address is emailed twice within `OUTREACH_COOLDOWN_DAYS` (default
    30), across campaigns and ideas → `blocked`;
  - no duplicates: one message per (campaign, contact); a sent message is never resent (row lock
    + status check);
  - bounces: an SMTP recipient refusal marks the message `bounced` and suppresses the address
    (`bounced`). Asynchronous bounce emails can be recorded by hand (`POST /messages/{id}/bounce`);
    reading the inbox is Phase 3;
  - unsubscribe: every message carries a signed link (`/unsubscribe/{token}`, HMAC of the
    message id) to a confirm page (GET shows it, POST confirms, so link scanners can't
    unsubscribe anyone), plus `List-Unsubscribe` / `List-Unsubscribe-Post` headers (RFC 8058).
    The footer also says *reply "stop" and I won't write again*; until Phase 3 reads replies, the
    user adds those by hand. The link works for real recipients only once the API is public
    (Phase 5);
  - transparent sender identity: `From` is the configured real name and address; the footer
    repeats who is writing and why. No fake company identities. Optional postal address line.
- **Deletion (PRD §37, from 1D):** `DELETE /ideas/{id}/contacts/{contact_id}` adds every known
  address of that contact (contact email, and any `to_email` on their messages) to
  `suppressions` with reason `deletion_request`, deletes their unsent messages, and **redacts**
  their sent ones: status, dates, cited evidence ids and `content_hash` stay; address, name,
  subject and body become `[deleted on request]`.
- **Tracking (PRD §19):** per campaign: drafted, approved, rejected, sent, bounced, blocked.
  Delivered = sent and not bounced. Replies arrive in Phase 3. Open rates are not tracked.

## Out of scope

Reply ingestion and analysis, IMAP bounce parsing (Phase 3). Sequences or automated follow-ups.
Bulk sending. Open/click tracking. Auth and a public deployment (Phase 5).

## Data model

| Table | Key columns |
|---|---|
| `outreach_campaigns` | idea_id, name, icp_id?, purpose, daily_limit, status (`active` / `paused`) |
| `messages` | campaign_id, contact_id? (SET NULL), company_id? (SET NULL), to_name, to_email?, to_email_source, subject, body, why_selected, cited_evidence_ids (json), checks (json), status, draft_error, approved_hash, approved_at, sent_at, sent_headers (json), sent_body, content_hash, provider_message_id, send_error, bounced_at, redacted_at; unique (campaign_id, contact_id) |
| `suppressions` | email (unique, lower-cased), reason (`unsubscribed` / `bounced` / `manual` / `deletion_request`), message_id?, note, created_at |

`sent_body` is the exact text sent (body + footer); `content_hash` covers the exact headers and
body. Cited evidence ids are stored on the message, so the evidence behind a sent message is
always recoverable.

## API

- `GET/POST /ideas/{id}/campaigns`, `GET/PATCH /ideas/{id}/campaigns/{cid}` (with stats).
- `POST /ideas/{id}/campaigns/{cid}/drafts` `{contact_ids}` → creates `drafting` messages and
  enqueues `draft_outreach_job`.
- `GET /ideas/{id}/campaigns/{cid}/messages`, `GET /ideas/{id}/messages/{mid}` (with prospect,
  score and cited evidence).
- `PATCH /ideas/{id}/messages/{mid}` (to_email, subject, body), `POST …/approve`,
  `POST …/reject`, `POST …/reopen`, `POST …/bounce`, `POST …/redraft`.
- `POST /ideas/{id}/campaigns/{cid}/send` `{message_ids?}` → enqueues `send_campaign_job` for
  approved messages (all, or the given ones).
- `GET/POST /suppressions`, `DELETE /suppressions/{id}` (only `manual` entries).
- `GET/POST /unsubscribe/{token}` (public, HTML).
- `GET /outreach/settings` → sender identity, whether sending is enabled, limits, today's usage.

## Jobs

- `draft_outreach_job(message_ids)`: builds each draft via `LLMRouter` and saves it.
- `send_campaign_job(campaign_id, message_ids?)`: for each approved message, locks the row and
  re-checks approval + hash, suppression, cooldown, daily limits and duplicates immediately
  before sending; records the exact content, headers and provider message id.

## LLM tasks

| Task | Provider | Notes |
|---|---|---|
| `draft_outreach` | local → Gemini fallback | Cited evidence ids are checked with `verify_citations`. |

## UI

New dossier folder tab **Outreach** (`/ideas/[id]/outreach`), in the Dossier design
(shadcn/ui, Instrument Serif / Geist, paper / ink):
- campaign list with stats and a "new campaign" sheet; a sender/limits strip (sending
  enabled?, today's usage);
- **email workspace** (PRD §42) per campaign: a message ledger with status stamps on the left;
  on the right the prospect, its score, why selected, cited exhibits (`EX-nn` chips), checks,
  editable to / subject / body, and **Approve**, **Reject**, **Send** (only for approved);
- an "add recipients" sheet listing contacts of the idea's prospects (score, role, email if
  public; already-messaged and suppressed marked);
- a suppression list sheet.

## Sender setup

- **Dev:** `docker compose up -d` starts Mailpit; `.env` has `SMTP_HOST=127.0.0.1`,
  `SMTP_PORT=1025`, no TLS. Open `http://localhost:8025` to read what was "sent".
- **Real (MVP):** a personal Gmail with 2-Step Verification and an app password:
  `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_STARTTLS=true`, `SMTP_USERNAME`,
  `SMTP_PASSWORD`. Keep volume tiny (Gmail limits and spam filters).
- **Later, dedicated domain:** publish SPF (`v=spf1 include:<provider> -all`), sign with DKIM
  at the provider, and add DMARC (`v=DMARC1; p=none; rua=mailto:…`, tighten to `quarantine`
  once reports are clean). Warm up slowly.
- **Legal:** this MVP stays very small. Legal review is required before contacting the US/EU at
  scale (PRD §37); messages are research requests, not marketing, but still carry an
  unsubscribe, a real identity and, optionally, a postal address.

## Acceptance criteria

- [ ] An unapproved message cannot be sent (tested at the service and job level).
- [ ] Suppressed addresses are never contacted; unsubscribing works end to end.
- [ ] Send limits and duplicate prevention are enforced (tested).
- [ ] Every sent message is stored with its exact content and cited evidence.
- [ ] Deleting a contact suppresses their address and redacts their messages (tested).
- [ ] Draft citations are verified; empty drafts never get filler text (tested).
- [ ] Web lint, typecheck and build pass; the outreach flow is checked in a real browser
      (draft → edit → approve → send to Mailpit → unsubscribe).

## Decisions (2026-11-03)

- Recipient address: public email if known, otherwise entered by the user on the draft.
- Sending: one SMTP provider; Mailpit for dev and verification; a Gmail app password for real
  sends. Dedicated-domain SPF/DKIM/DMARC guidance is above.
- Contact deletion after a send: delete unsent drafts, redact sent messages but keep their
  hash, suppress the address.
- Unsubscribe: real signed link + confirm page + List-Unsubscribe headers, and a *reply "stop"*
  line in the footer handled by hand until Phase 3.
- Messages point at a contact (a person), not only a company: a prospect is a company, and
  outreach goes to someone at it.

## Notes

- From 1D: contact deletion must suppress the address (covered above).
