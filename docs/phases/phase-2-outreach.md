# Phase 2 — Outreach

- **Status:** Not started (draft)
- **Goal:** Send a small number of honest, research-oriented messages to well-chosen prospects,
  with a human approving every one.
- **PRD refs:** §17 Outreach generation, §18 Human approval gate, §19 Outreach experiment,
  §36 Safety & deliverability, §37 privacy, §42 Email workspace

## Scope

- **Drafting** (`draft_outreach`, local, Gemini fallback). Each draft:
  - names the recipient and says why they were selected;
  - may cite real public evidence (by evidence id);
  - states the research purpose and asks one small question;
  - never claims the product exists if it doesn't;
  - never exaggerates.
- **Approval gate:** `draft → approved | rejected`; `approved → sent`. Sending a message that
  isn't approved is impossible, enforced in the service and covered by tests.
- **Email provider interface:** `EmailProvider`, first implemented as SMTP (e.g. a Gmail app
  password). Credentials live only in `.env`.
- **Safety (PRD §36):**
  - daily and per-campaign send limits;
  - a global suppression list;
  - an unsubscribe link and its handling;
  - no duplicate sends;
  - contact frequency limits;
  - bounce recording;
  - a transparent sender identity (real name and reason), and no fake company identities.
  - **from 1D:** deleting a contact (`DELETE /ideas/{id}/contacts/{contact_id}`) must also add
    their email, if known, to `suppressions` with reason `deletion_request`.
- **Tracking (PRD §19):** sent, delivered or bounced, replied (Phase 3 fills in replies). Open
  rates are not used as validation.

## Out of scope

Reply ingestion and analysis (Phase 3). Sequences or automated follow-ups. Bulk sending.

## Data model (draft)

| Table | Key columns |
|---|---|
| `outreach_campaigns` | idea_id, name, icp_id?, daily_limit, status |
| `messages` | campaign_id, prospect_id, subject, body, cited_evidence_ids (json), status (`draft` / `approved` / `rejected` / `sent` / `bounced`), approved_at, sent_at, provider_message_id |
| `suppressions` | email (unique), reason (`unsubscribed` / `bounced` / `manual` / `deletion_request`), created_at |

## API (draft)

- `POST /campaigns`, `POST /campaigns/{id}/drafts` (generate drafts for selected prospects).
- `PATCH /messages/{id}` (edit), `POST /messages/{id}/approve`, `POST /messages/{id}/reject`.
- `POST /campaigns/{id}/send`, which enqueues approved messages within the limits.
- `GET /unsubscribe/{token}` (public).

## Jobs

`send_job(campaign_id)`: re-checks approval, suppression, limits and duplicates immediately
before each send.

## LLM tasks

| Task | Provider | Notes |
|---|---|---|
| `draft_outreach` | local → Gemini fallback | Cited evidence ids are checked with `verify_citations`. |

## UI

Email workspace (PRD §42): prospect, score, evidence, editable draft, Approve & send / Reject.

## Acceptance criteria

- [ ] An unapproved message cannot be sent (tested at the service and job level).
- [ ] Suppressed addresses are never contacted; unsubscribing works end to end.
- [ ] Send limits and duplicate prevention are enforced (tested).
- [ ] Every sent message is stored with its exact content and cited evidence.

## Open questions (settle at kickoff)

- Sender domain: a personal Gmail, or a dedicated domain (SPF / DKIM / DMARC guidance)?
- Legal review before contacting the US/EU at scale (PRD §37). This MVP stays very small.
