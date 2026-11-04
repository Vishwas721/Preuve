# Phase 5B — Privacy

- **Status:** Not started (draft)
- **Goal:** Make personal data easy to find, export and delete, and keep only what's needed.
- **PRD refs:** §37 Privacy & compliance

## Scope (draft)

- **Contact export:** everything Preuve holds about one person (contact row, messages, replies,
  interview notes, WTP records, derived evidence, suppression status) as JSON.
- **Deletion:** already removes replies, notes, WTP and derived evidence and suppresses the
  address (Phases 1D/3). Audit that nothing personal survives (sent message bodies, report
  content that quotes them, Mailpit/GreenMail aside), and keep a minimal deletion log
  (hashed email, date) so a deleted person isn't re-imported and contacted again.
- **Retention:** fetched page text (`sources.full_text`, kept since 1B for re-verification) —
  decide a retention rule (e.g. drop `full_text` after N days, keep the quote and a hash);
  sent message bodies after N days; reports quoting deleted people.
- **Provenance audit:** a check (endpoint + test) that every contact and evidence item has a
  source URL, fetched-at time and verbatim quote; list violations.

## Acceptance criteria (draft)

- [ ] Deleting a contact removes their personal data everywhere and suppresses the address.
- [ ] A contact's data can be exported.
- [ ] Retention rules run on schedule and are tested.
- [ ] The provenance audit reports zero violations on the real database.

## Open questions

- Retention periods.
