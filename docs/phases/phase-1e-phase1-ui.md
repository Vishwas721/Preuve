# Phase 1E — Phase 1 UI

- **Status:** In progress (kickoff 2026-11-02)
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

## Decisions (2026-11-02)

- **Component library: shadcn/ui** on Radix primitives (accessible dialogs, sheets, selects,
  tabs, tooltips, plus a `cmdk` command palette), with **motion** for animation,
  **lucide-react** for icons and **sonner** for toasts. Components are copied into the repo, so we
  own them and can restyle them fully.
- **Design direction: "The Dossier".** Preuve is French for *proof*, so the UI reads like an
  evidence case file rather than a generic SaaS dashboard:
  - **Typography:** an editorial serif display face (Instrument Serif) for headlines and quoted
    evidence, Geist for UI text, and Geist Mono for metadata (exhibit numbers, dates, domains,
    scores).
  - **Surfaces:** warm paper (light) and deep ink (dark), with a subtle grain, hairline rules,
    and folder tabs for case navigation.
  - **Evidence:** each item is an **exhibit** (`EX-07`) with a large serif pull-quote, a source
    line in mono, and **stamps** (`VERIFIED` / `UNVERIFIABLE`) styled like rubber stamps.
    Fact, inference and assumption always look different.
  - **Data viz (dataviz method, palette validated on these surfaces):**
    - the evidence balance (supports ↔ contradicts) uses the diverging pair, blue ↔ red with a
      gray neutral;
    - scores and rubrics are single-hue blue bars with tracks;
    - verification uses status colors, always with an icon and a label;
    - every chart gets a tooltip and a text alternative.
  - **Navigation:**
    - a slim top bar and a ⌘K command palette (jump to any idea or section);
    - the idea **dossier** has a sticky "case file" rail (verdict balance, counts, open
      questions) and folder-tab sections.
- **Routes:**
  - `/` is the case board (portfolio);
  - `/ideas/new` is intake ("What are you thinking of building?", per PRD §50);
  - `/ideas/[id]` is Overview (hypothesis, open questions, ICPs);
  - `/ideas/[id]/evidence` is the research explorer;
  - `/ideas/[id]/landscape` covers competitors and alternatives;
  - `/ideas/[id]/prospects` is the prospect explorer.
  A shared `layout.tsx` loads the idea once and polls while runs or imports are active.
- **One read endpoint:** `GET /portfolio` returns per-idea aggregates (evidence by stance and
  verification, competitors, prospects and the top score, open and answered unknowns, last
  activity). It's a new `portfolio` module that only calls other modules' service functions.
- **Dark mode is first-class:** its own tokens (validated chart colors), a theme toggle, and
  respect for the OS setting.
- **Still out of scope:** deleting research imports (noted in 1B). It's a backend feature, not
  UI polish; revisit after Phase 1.
