# Phase 5B — Privacy

- **Status:** In progress (kickoff 2026-11-04)
- **Goal:** Make personal data easy to find, export and delete, keep only what's needed, and
  prove every exhibit and contact has a source.
- **PRD refs:** §37 Privacy & compliance (minimise, deletion, suppression, provenance, no
  sensitive data), §36 (suppression lists)

## What personal data Preuve holds (audit at kickoff)

| Where | What | Deleted with the person today? |
|---|---|---|
| `contacts` | name, role, email (only if printed on a page), source URL | yes (1D) |
| `evidence` row behind a contact | a quote like "Dave Gover, Director of Operations" | **no** |
| `messages` | to-name, address, subject, body, headers | redacted (2) |
| `responses` + their `preuve://` source and evidence | the reply text, sender | yes (3) |
| `interviews`, notes, their evidence | name, role, notes | yes, when linked to the contact (3) |
| `wtp_signals` | label, quotes, commitments | yes, when linked to the contact (3) |
| `reports.content` | verbatim reply/interview quotes | **no** |
| `validation_scores.inputs` | customer keys; a reply without a contact is keyed by its sender's **email** | **no** |
| `sources.text/full_text` (research) | whole public pages, sometimes listing other people | kept forever (1B) |
| `suppressions` | the address (needed to keep blocking it) | kept on purpose |

## Scope

### Deletion that leaves nothing behind

- Deleting a contact (existing endpoint) now also:
  - deletes the evidence row naming them, when nothing else uses it (no unknown, competitor or
    other-contact link, not a company's size/location evidence);
  - deletes every **report** that quoted evidence being deleted (reports can be regenerated);
    the same applies when a reply or an interview is deleted;
  - records a **tombstone** (SHA-256 of the email, and of company domain + name key) so a later
    research import doesn't recreate the person; such contacts are rejected with "deleted on
    request".
- Score inputs never hold raw emails or names: customers without a contact are keyed by a hash.

### Find, export and erase a person (data-subject requests)

- In the active workspace, by **email address** (how requests arrive) or by contact:
  - **find**: contacts, messages to the address, replies from it, interviews and WTP records
    linked to those contacts, suppression status;
  - **export**: all of it as one JSON file (contact and source, messages with bodies, replies,
    interview notes, WTP, first-party evidence, suppression), plus a short explanation of where
    the data came from;
  - **erase**: delete every matching contact as above, delete replies from the address, redact
    messages to it, suppress the address and write the tombstone.

### Retention (agreed at kickoff)

- **Research page text:** kept 30 days after it was fetched, then `text` and `full_text` are
  dropped by a daily job. URL, fetch time, title, verified quote and the page's content hash
  stay, so every exhibit remains traceable and can be re-checked by fetching again. First-party
  (`preuve://`) sources are not touched: they live and die with their reply or interview.
- **Never-contacted prospects:** not deleted automatically; the privacy check lists contacts
  with no outreach for 180+ days, with a delete action.

### Privacy and provenance check

`GET /privacy/check` (active workspace), deterministic:

- **provenance:** evidence without source URL, fetch time or quote; contacts without source
  evidence, or whose source quote doesn't contain their name; contacts with an email that isn't
  marked as found on a page or entered by the user;
- **minimisation:** never-contacted contacts older than 180 days; contact emails at free-mail
  domains (personal, not professional, addresses);
- **retention:** research sources still holding text past 30 days (the job is behind);
- **suppressions** with no workspace (legacy rows).

Each finding has a kind, a plain-language message and the ids involved. Empty → "No issues
found."

## Out of scope

Deleting data from the mailboxes themselves (Mailpit/GreenMail/Gmail) and from backups (5D will
document backup rotation). A sensitive-data scanner (PRD §37 "avoid sensitive personal data")
beyond the minimisation checks above. Retention of sent messages and replies (kept as the record
of what was said; deleted on request).

## Data model

| Table | Change |
|---|---|
| `deleted_people` (new) | email_hash?, person_hash? (domain + name key), reason, deleted_at — no plain personal data |
| `sources` (changed) | + `text_purged_at` |

## API

- `GET /privacy/people?email=…` (find), `GET /privacy/people/export?email=…` or
  `?contact_id=…` (JSON download), `POST /privacy/people/erase` `{email}`.
- `GET /privacy/check`.
- Existing `DELETE /ideas/{id}/contacts/{cid}` gains the extra clean-up.

## Jobs

`purge_page_text` (arq cron, daily): drops research page text older than 30 days.

## UI

Settings → **Privacy**: look up a person by email (what we hold, export JSON, erase with a
confirmation), and the privacy check with its findings (delete stale prospects from there).

## Acceptance criteria

- [ ] Deleting a contact removes their personal data everywhere (including reports and the
      evidence naming them) and suppresses the address (tested).
- [ ] A deleted person isn't recreated by a later research import (tested).
- [ ] A person's data can be found and exported by email; erase-by-email works (tested).
- [ ] No raw email or name is stored in score inputs (tested).
- [ ] Research page text is dropped after 30 days by the scheduled job; exhibits stay
      traceable (tested).
- [ ] The privacy check reports zero provenance violations on the real database.
- [ ] Web lint, typecheck and build pass; lookup, export, erase and the check work in a real
      browser.

## Decisions (2026-11-04)

- Page text: 30 days, then dropped (hash, URL, quote kept).
- Never-contacted prospects: flagged after 180 days, not auto-deleted.
- Reports quoting deleted data are deleted, not redacted (they're cheap to regenerate and a
  redacted report would misstate its own evidence).
- Tombstones and suppressions are instance-wide (one operator per install), stored as hashes.

## Notes

- 5A: everything is scoped to the active workspace; tombstones are global like suppression
  blocking.
- Restart the arq worker after pulling (new cron job).
