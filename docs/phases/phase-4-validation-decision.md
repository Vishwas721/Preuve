# Phase 4 — Validation & decision

- **Status:** Not started (draft)
- **Goal:** Combine all stored evidence into a reproducible score, a validation state and an
  explained recommendation, including telling the founder "don't build yet".
- **PRD refs:** §24 Validation scoring, §25 Validation states, §26 Decision engine,
  §27 Portfolio, §28 Experiments, §44 Validation report, §47–§48 metrics, §51 philosophy

## Scope

- **Validation score (PRD §24 weights):**
  - problem evidence 20, frequency 10, severity 15, customer response 15, interview
    confirmation 15, existing alternatives 10, willingness to pay 15;
  - computed **only from stored data** by deterministic rules; the LLM never invents a number;
  - each dimension stores its points, reason and evidence ids.
- **Validation states (PRD §25):** rule-based transitions (e.g. "problem validated" needs N
  independent customers confirming it) that update `ideas.state`.
- **Decision engine (PRD §26):** BUILD / ITERATE / INVESTIGATE FURTHER / ABANDON, with:
  - strong evidence, weak evidence and the biggest uncertainty;
  - the next action (usually the open unknowns plus missing dimensions).
- **Experiments (PRD §28):** hypothesis, ICP, sample, result, conclusion. They compare cohorts
  (e.g. ops directors vs PMs) using response data.
- **Validation report (PRD §44):** generated narrative (`validation_report`, Gemini). Every claim
  is cited; it is exportable as Markdown or PDF.
- **Portfolio comparison (PRD §27):** compare ideas by score, evidence, responses, interviews and
  WTP.
- **Metrics (PRD §47–§48):** validated customer conversations per idea (the north star),
  response rate, problem confirmation rate, interview conversion.

## Out of scope

Automated experiment generation, landing pages, pre-orders (PRD §49 future features).

## Data model (draft)

| Table | Key columns |
|---|---|
| `validation_scores` | idea_id, total, dimensions (json: name, points, max, reason, evidence_ids), state, recommendation, computed_at, inputs_hash |
| `experiments` | idea_id, hypothesis, icp_id?, sample_size, result (json), conclusion, status |
| `reports` | idea_id, validation_score_id, content (md), created_at |

## API (draft)

- `POST /ideas/{id}/score` (recompute) and `GET /ideas/{id}/score`.
- `GET/POST /ideas/{id}/experiments`, `PATCH /experiments/{id}`.
- `POST /ideas/{id}/report` (job) and `GET /reports/{id}`.
- `GET /portfolio`.

## LLM tasks

| Task | Provider | Notes |
|---|---|---|
| `validation_report` | Gemini chain | Narrative only; numbers come from the DB; `verify_citations` enforced. |

## UI

Score card with dimension breakdown, state badge, recommendation panel, experiments list, report
view, portfolio comparison table.

## Acceptance criteria

- [ ] The score is fully reproducible from DB data (same inputs, same output; tested).
- [ ] Every recommendation lists the evidence behind it, plus its weak spots.
- [ ] A fixture idea with weak evidence is told not to build yet (tested).
- [ ] The report contains only cited claims; numbers match the score record.

## Open questions (settle at kickoff)

- Exact thresholds for each state transition (e.g. how many independent confirmations).
