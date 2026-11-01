# Phase 1C — Competitors & alternatives

- **Status:** Not started (draft)
- **Goal:** Answer "how is this problem solved today?" with sourced entries only.
- **PRD refs:** §13 Competitor & alternative analysis, §35 guardrails

## Scope

- **Discovery:** targeted searches (e.g. "<problem> software", "<problem> template",
  "<problem> consultant") plus mentions already in Phase 1B sources and the founder's list of
  known competitors.
- **Classification** into four kinds:
  - **direct**: products solving the same problem;
  - **indirect**: different software solving part of it;
  - **manual**: Excel, Sheets, email, paper, WhatsApp, internal tools;
  - **service**: consultants, agencies, freelancers.
- **Each entry** has: name, url, kind, what it covers, pricing if publicly stated, the evidence
  ids that mention it, and how customers talk about it (praise or complaints) when the sources
  say so.
- **"Current solutions" summary** (`analyze_competitors`, Gemini): claims that must pass
  `verify_citations`. Without sources the summary says "No evidence found."

## Out of scope

Pricing strategy and positioning advice. Feature-by-feature comparison matrices.

## Data model (draft)

| Table | Key columns |
|---|---|
| `competitors` | idea_id, name, url, kind, description, pricing_note?, source (`ai` / `user`), dismissed |
| `competitor_evidence` | competitor_id, evidence_id |

## API (draft)

- `POST /ideas/{id}/competitors/discover` (job) and `GET /ideas/{id}/competitors`.
- `POST /ideas/{id}/competitors` (manual add) and `PATCH/DELETE /competitors/{id}`.

## Jobs

`competitor_job(idea_id)`: search → fetch → reuse the evidence pipeline → group into competitors
→ synthesize.

## LLM tasks

| Task | Provider | Notes |
|---|---|---|
| `extract_fields` | local | Pull the product name, kind and claims from a page. |
| `analyze_competitors` | Gemini chain | Grouping and summary; every claim must cite evidence. |

## UI

A "How it's solved today" section on the idea page, grouped by kind, with source links.

## Acceptance criteria

- [ ] Every competitor or alternative links to at least one evidence item, or is marked "added
      by user".
- [ ] Manual and service alternatives appear when the sources mention them.
- [ ] The summary contains only cited claims; empty input gives "No evidence found."
- [ ] The user can add, edit and dismiss entries.

## Open questions (settle at kickoff)

- Should founder-listed competitors be fetched and verified automatically?
