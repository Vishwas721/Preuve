# Phase 1E — Phase 1 UI

- **Status:** Not started (draft)
- **Goal:** Make Phase 1 usable end to end in the browser: from a new idea to ranked prospects,
  with the evidence one click away.
- **PRD refs:** §27 Portfolio, §38 Dashboard, §39 Idea detail, §40 Research explorer,
  §41 Prospect explorer, §46 MVP success criteria (items 1–6)

## Scope

- **Portfolio dashboard:** all ideas with state, counts (evidence, prospects) and last activity.
  The score column waits for Phase 4.
- **Idea detail:** problem, hypothesis, unknowns (answered or open), ICPs, evidence summary,
  competitors, prospects summary, next actions (the open unknowns).
- **Research explorer:** evidence list with filters (type, kind, relevance, unknown, source).
  Opening an item shows the source, date, quote, why it's relevant and the linked hypothesis.
- **Prospect explorer:** filters (industry, size, location, role, score, evidence, status), sort
  by score, and a score breakdown panel.
- **Progress views** for analysis, research and discovery runs.
- **Shared UI basics:** layout and navigation, loading, empty and error states, responsive
  layout, accessible components.

## Out of scope

Outreach (Phase 2). Validation score and report (Phase 4). Auth (Phase 5).

## Data model / API

No new tables. Only small read endpoints if a view needs aggregated counts (e.g.
`GET /ideas/{id}/summary`).

## UI notes

- A fact, an inference and an assumption must look different everywhere (PRD §12).
- "No evidence found." is shown wherever a list is empty because nothing was found.

## Acceptance criteria

- [ ] For one fresh idea, PRD §46 items 1–6 are reachable in the UI: ICP, hypotheses, evidence,
      competitors, 20+ prospects, lead scores.
- [ ] Every evidence item and score component links back to its source.
- [ ] Empty, loading and error states exist for every view.
- [ ] Web lint, typecheck and build pass; key flows are checked manually in a browser.

## Open questions (settle at kickoff)

- Should we add a component library (e.g. shadcn/ui), or stay with plain Tailwind?
