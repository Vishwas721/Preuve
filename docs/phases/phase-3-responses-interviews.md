# Phase 3 — Responses & interviews

- **Status:** Not started (draft)
- **Goal:** Turn replies and interviews into structured, first-party evidence: the strongest
  kind Preuve collects.
- **PRD refs:** §20 Response intelligence, §21 Conversation intelligence, §22 Interview
  workspace, §23 Willingness-to-pay, §43 Response dashboard

## Scope

- **Reply ingestion:** manual paste first; then IMAP polling for the sending mailbox, matched to
  sent messages.
- **Response intelligence** (`classify_response`, local): sentiment, problem confirmed, frequency,
  current solution, time or cost, severity, satisfaction with the current solution, interest,
  recommended action (PRD §20).
- **Conversation intelligence** for longer threads and interview notes: problem, workflow,
  frequency, cost, alternatives, trigger, buyer, decision process, objections, desired solution
  (PRD §21).
- **First-party evidence:** each extracted signal becomes `evidence` of kind `fact`, linked to the
  response or interview, with the customer's verbatim words as the quote.
- **Interview workspace:**
  - guides generated from open unknowns, with neutral, non-leading questions (PRD §22);
  - scheduling notes, live notes and a post-interview extraction;
  - answered unknowns are marked as such.
- **Willingness to pay (PRD §23):** current spend, estimated problem cost, expected price, stated
  willingness, actual commitment (with stated and committed kept clearly separate).

## Out of scope

Calendar integrations. Call recording or transcription (possible later). The validation score
(Phase 4).

## Data model (draft)

| Table | Key columns |
|---|---|
| `responses` | message_id?, prospect_id, raw_text, received_at, channel (`paste` / `imap`), classification (json) |
| `interviews` | idea_id, prospect_id?, scheduled_at, status, guide (json) |
| `interview_notes` | interview_id, text, extracted (json), created_at |
| `wtp_signals` | idea_id, prospect_id, current_spend?, problem_cost?, expected_price?, stated_willingness, commitment (`none` / `verbal` / `pilot` / `signed` / `paid`), evidence_id |

## API (draft)

- `POST /responses` (paste) and `GET /ideas/{id}/responses`.
- `POST /ideas/{id}/interviews`, `POST /interviews/{id}/guide`, `POST /interviews/{id}/notes`.
- `GET/POST /ideas/{id}/wtp`.

## Jobs

`imap_poll_job` (periodic), `analyze_response_job(response_id)`,
`analyze_interview_job(interview_id)`.

## LLM tasks

| Task | Provider | Notes |
|---|---|---|
| `classify_response` | local | Precise label definitions (benchmark lesson). |
| `extract_fields` | local | Conversation fields from notes. |
| `synthesize_evidence` | Gemini chain | Response dashboard summary; cited claims only. |

Private correspondence defaults to **local** processing (ADR 0002 privacy note).

## UI

Responses inbox with classifications, interview workspace (guide, notes, extraction), and the
response dashboard (PRD §43).

## Acceptance criteria

- [ ] A pasted reply becomes a structured record and `fact` evidence quoting the reply.
- [ ] IMAP replies are matched to the right prospect and message.
- [ ] Interview guides come only from open unknowns; questions are non-leading (reviewed).
- [ ] WTP records separate stated willingness from actual commitment.

## Open questions (settle at kickoff)

- IMAP provider specifics (Gmail app password + IMAP).
- Should Gemini be allowed for private replies at all (opt-in setting)?
