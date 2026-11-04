# Phase 3 — Responses & interviews

- **Status:** In progress (kickoff 2026-11-04)
- **Goal:** Turn replies and interviews into structured, first-party evidence: the strongest
  kind Preuve collects.
- **PRD refs:** §20 Response intelligence, §21 Conversation intelligence, §22 Interview
  workspace, §23 Willingness-to-pay, §37 Privacy, §43 Response dashboard

## Scope

### Replies

- **Ingestion, two channels:**
  - **paste:** pick the sent message it answers (or none), paste the text, optionally set the
    sender and date;
  - **IMAP polling** of the sending mailbox (`imap_poll_job`, every few minutes, plus a "Check
    inbox now" button). Only unseen messages newer than the oldest sent outreach are read; each
    is deduplicated by its `Message-ID`.
- **Matching** an IMAP email to the outreach message it answers, in order:
  1. `In-Reply-To` / `References` contain our `<message-uuid@domain>` id;
  2. otherwise the sender's address equals the `to_email` of exactly one sent message (the most
     recent within 60 days).
  Unmatched emails are **not stored** (they're not outreach replies; minimal data, PRD §37).
- **Bounces over IMAP:** delivery-status reports (`multipart/report; report-type=delivery-status`)
  quoting our Message-ID mark that message `bounced` and suppress the address. They aren't stored
  as replies.
- **Opt-outs:** a clear opt-out ("stop", "unsubscribe", "remove me", "don't contact/email me"…)
  near the start of a reply suppresses the sender (reason `unsubscribed`) and labels the reply
  `opt_out`. It is still classified, but never turned into a recommendation to follow up.
- **Response intelligence** (`classify_response`, local), PRD §20: sentiment
  (`positive` / `neutral` / `negative`), problem confirmed (`yes` / `no` / `unclear`),
  frequency, current solution, time or cost, severity, satisfaction with the current solution,
  interest, and recommended action (`interview` / `follow_up` / `close` / `none`). Every
  non-empty field carries the customer's **verbatim quote**; precise label definitions are in
  the prompt; "unclear" / empty when the reply doesn't say.
- **First-party evidence:** each classified signal whose quote is found verbatim in the reply
  (the research matcher) becomes `evidence` of kind `fact`, `origin = reply`, linked to the
  response and to its company, with the customer's words as the quote. Signals whose quote isn't
  found are dropped and counted in the response's `dropped` list. The user can dismiss any item,
  as with research evidence.

### Interviews

- **Interview record:** interviewee (a contact, or a free-text name and role), company,
  scheduled time, status (`planned` / `done` / `cancelled`), scheduling note.
- **Guide** (`interview_guide`, local; not private: only the hypothesis and unknowns go in):
  built **only from open unknowns**. Each question cites its unknown id (verified), has 1–2
  follow-ups, and passes deterministic **leading-question checks** (yes/no openers such as
  "Do you / Would you / Don't you / Isn't it", "wouldn't it be great", "how much would you pay
  for our…", mentions of the product). Questions that fail are flagged, not silently kept. The
  guide also lists what's already *known* (cited research claims), as in PRD §22.
- **Notes:** timestamped notes during or after the interview (`live` / `post`).
- **Extraction** (`extract_fields`, local, private), PRD §21: problem, workflow, frequency,
  cost, alternatives, trigger, buyer, decision process, objections, desired solution, and
  which open unknowns the notes answer. Same rule as replies: only verbatim-quoted fields become
  `fact` evidence (`origin = interview`).
- **Answered unknowns:** the extraction *proposes* answered unknowns; the user confirms each
  one, which links the evidence to the unknown and sets it to `answered`.

### Willingness to pay (PRD §23)

- A ledger per idea: customer, current spend, estimated problem cost, expected price, **stated
  willingness** (`none` / `low` / `some` / `strong`, with the quote), and **actual commitment**
  (`none` / `verbal` / `pilot` / `signed` / `paid`, with a note and date).
- Stated and committed are separate fields, shown separately. The AI may *propose* a stated
  willingness from a quote; **only the user can set a commitment** above `none`.

### Response dashboard (PRD §43)

Deterministic counts, no LLM: sent, replies, reply rate, positive / neutral / negative, opt-outs,
problem confirmed, interview recommended, interviews done, pilot-or-better commitments, and the
most common pain (the most frequent problem quotes, shown verbatim, grouped by exact
frequency/current-solution labels).

## Privacy

- Reply text and interview notes are private. Their LLM tasks call the router with
  `private=True`: they run on the local model only, unless `ALLOW_PRIVATE_TO_GEMINI=true`
  (default `false`) lets them escalate to Gemini.
- Deleting a contact also deletes their replies, interview notes, WTP records and the evidence
  derived from them (first-party evidence is personal data), and suppresses the address.
- Unmatched mailbox email is never stored.

## Out of scope

Calendar integrations. Call recording or transcription. Automated follow-ups. The validation
score (Phase 4).

## Data model

Earlier tables are extended, not duplicated:

| Table | Change / key columns |
|---|---|
| `evidence` (1B) | `import_id` becomes nullable; new `origin` (`research` / `reply` / `interview`), `response_id?`, `interview_id?` (CASCADE). First-party evidence gets a `sources` row with URL `preuve://responses/{id}` or `preuve://interviews/{id}`, fetched-at = received/held time, and the full text, so quotes stay verifiable. |
| `responses` | idea_id, message_id? (SET NULL), contact_id? / company_id? (SET NULL), from_name, from_email, subject, raw_text, received_at, channel (`paste` / `imap`), rfc_message_id (unique, dedupe), status (`queued` / `analyzing` / `done` / `failed`), opt_out, classification (json), dropped (json), error |
| `interviews` | idea_id, contact_id? / company_id? (SET NULL), interviewee_name, interviewee_role, scheduled_at?, status, scheduling_note, guide (json), guide_status, extraction (json), extraction_status, error |
| `interview_notes` | interview_id, kind (`live` / `post`), text, created_at |
| `wtp_signals` | idea_id, contact_id? / company_id?, response_id? / interview_id?, customer_label, current_spend, problem_cost, expected_price, stated_willingness, stated_quote, stated_evidence_id?, commitment, commitment_note, committed_at, source (`user` / `ai`) |

## API

- Replies: `GET /ideas/{id}/responses`, `POST /ideas/{id}/responses` (paste),
  `GET /ideas/{id}/responses/{rid}`, `POST …/reanalyze`, `DELETE …` (removes derived evidence).
- Mailbox: `POST /outreach/inbox/check` (enqueue a poll), `GET /outreach/inbox` (enabled?, last
  poll, counts).
- Interviews: `GET/POST /ideas/{id}/interviews`, `GET/PATCH /ideas/{id}/interviews/{iid}`,
  `POST …/guide` (generate), `POST …/notes`, `DELETE …/notes/{nid}`, `POST …/extract`,
  `POST …/unknowns/{uid}/confirm`.
- WTP: `GET/POST /ideas/{id}/wtp`, `PATCH/DELETE /ideas/{id}/wtp/{wid}`.
- Dashboard: `GET /ideas/{id}/responses/dashboard`.

## Jobs

`imap_poll_job` (arq cron, every 5 minutes when IMAP is configured, and on demand),
`analyze_response_job(response_id)`, `interview_guide_job(interview_id)`,
`analyze_interview_job(interview_id)`.

## LLM tasks

| Task | Provider | Notes |
|---|---|---|
| `classify_response` | local, `private=True` | Precise label definitions; every field quoted verbatim. |
| `extract_fields` | local, `private=True` | Conversation fields + answered-unknown proposals. |
| `interview_guide` (new) | local | Only open unknowns and the hypothesis; questions cite unknown ids. |

`synthesize_evidence` is not used: the dashboard is deterministic.

## UI (Dossier design)

- **Replies** tab: the response dashboard (PRD §43), the inbox (classification chips, opt-out
  and recommended-action stamps, "Check inbox now", "Paste a reply"), and a reply sheet with the
  original outreach, the verbatim reply with the quoted spans highlighted, the extracted signals
  and their `EX-nn` exhibits.
- **Interviews** tab: interview list; the interview workspace with known / unknown, the guide
  (question, follow-ups, leading-check flags), notes, extraction with answered-unknown
  confirmations; and the willingness-to-pay ledger (stated vs committed in separate columns).
- First-party exhibits get their own mark in the evidence explorer ("Reply" / "Interview").

## Acceptance criteria

- [ ] A pasted reply becomes a structured record and `fact` evidence quoting the reply.
- [ ] IMAP replies are matched to the right prospect and message (tested; live with GreenMail).
- [ ] IMAP bounce reports mark the message bounced and suppress the address (tested).
- [ ] Opt-out replies suppress the sender (tested).
- [ ] Interview guides come only from open unknowns; questions are non-leading (checked and
      reviewed).
- [ ] WTP records separate stated willingness from actual commitment; the AI can't set a
      commitment (tested).
- [ ] Private text never reaches Gemini unless opted in (tested).
- [ ] Deleting a contact removes their replies, notes, WTP records and derived evidence (tested).
- [ ] Web lint, typecheck and build pass; replies, interviews and WTP are checked in a real
      browser.

## Mail setup

- **Dev:** docker compose adds **GreenMail** (free test mail server): SMTP `3025`, IMAP `3143`,
  a `founder@preuve.local` / `secret` mailbox. Mailpit stays the outgoing catcher; to test
  replies, a script sends an email *into* GreenMail that answers a sent message.
- **Real:** Gmail IMAP with the same app password: `IMAP_HOST=imap.gmail.com`, `IMAP_PORT=993`,
  `IMAP_SSL=true`, `IMAP_USERNAME`, `IMAP_PASSWORD`, `IMAP_FOLDER=INBOX`. Leave `IMAP_HOST` empty
  to disable polling.

## Decisions (2026-11-04)

- IMAP via stdlib `imaplib`, matched by headers then sender; GreenMail for dev; paste always
  available.
- Private text is local-only unless `ALLOW_PRIVATE_TO_GEMINI=true`.
- Extracted signals become `fact` evidence automatically, but only when their quote is found
  verbatim; the user can dismiss them.
- Clear opt-out replies auto-suppress the sender.
- First-party evidence reuses the `evidence` table (with `origin`) so the explorer, citations and
  Phase 4 scoring treat it like any other evidence.

## Notes

- From Phase 2: "stop" replies and async bounces were manual; this phase automates both.
- Restart the arq worker after pulling (a stale worker swallows unknown job types).
