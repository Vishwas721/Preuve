# Phase 1A — Idea intake & analyzer

- **Status:** Not started (draft)
- **Goal:** Turn a raw idea into a structured, editable problem hypothesis, a list of unknowns
  (the research plan) and candidate ICPs. All of it is clearly labelled as AI assumptions.
- **PRD refs:** §8 Idea submission, §9 Idea analyzer, §10 ICP generator, §12 (fact / inference /
  assumption), §35 guardrails

## Scope

- **Idea intake form:** idea, target market, why it matters, plus the optional PRD §8 fields
  (industry, customer type, business model, known competitors, assumptions). Uses the existing
  `ideas` table.
- **Analyze idea** (`analyze_idea`, Gemini) produces a hypothesis:
  - problem statement;
  - potential users, potential buyer, decision maker;
  - potential economic value;
  - geography and industry.
- **Unknowns** (part of `analyze_idea` output): 3–8 concrete questions that research and
  interviews must answer (frequency, time and cost, current tools, budget owner, adequacy of
  existing solutions, ...). Each has a category and a priority.
- **Generate ICPs** (`generate_icps`, Gemini): 1–3 candidate ICPs, each with:
  - company type, size band, geography, operating signals (e.g. "10+ active projects");
  - target roles (user / buyer);
  - a hypothesis score from 0–100 built from a **fixed rubric** (see Decisions): the model rates
    each criterion 1–5 with a rationale, and code computes the weighted total.
- **Labelling:** every generated item is stored as an `assumption` until later phases attach
  evidence. The UI makes that obvious.
- **Editing:** the user can edit, delete, add and re-generate the hypothesis, unknowns and ICPs.
  Hypothesis edits and re-generations create a **new version** (append-only); the latest is
  current. Unknowns and ICPs aren't versioned: removing one sets its status instead of deleting it.
- **Async:** analysis runs as an arq job. The request returns a run id and the UI polls status.

## Out of scope

Web research and evidence (1B), competitors (1C), companies and prospects (1D).

## Data model (draft)

| Table | Key columns |
|---|---|
| `hypotheses` | idea_id, version (unique per idea), problem, users, buyer, decision_maker, economic_value, geography, industry, source (`ai` / `user`), change_note? — append-only |
| `unknowns` | idea_id, question, category, priority, status (`open` / `answered` / `dropped`), source |
| `icps` | idea_id, name, company_type, size_min, size_max, geography, signals (json), roles (json), score_components (json: criterion, rating 1–5, rationale), hypothesis_score (computed), source, is_primary, status (`active` / `dismissed`) |
| `analysis_runs` | idea_id, kind (`analyze` / `icps`), status, error, started_at, finished_at |

## API (draft)

- `POST /ideas/{id}/analyze` starts the analysis job and returns `analysis_run`.
- `GET /ideas/{id}/analysis-runs/{run_id}` returns run status.
- `GET /ideas/{id}/hypothesis` (current version), `GET /ideas/{id}/hypothesis/versions`, and
  `POST /ideas/{id}/hypothesis` (save an edit as a new version).
- `GET/POST /ideas/{id}/unknowns`, `PATCH/DELETE /unknowns/{id}`.
- `GET/POST /ideas/{id}/icps`, `PATCH/DELETE /icps/{id}`.

## Jobs

`analyze_idea_job(idea_id)` runs the hypothesis and unknowns first, then the ICPs, and stores
results plus run status.

## LLM tasks

| Task | Provider | Notes |
|---|---|---|
| `analyze_idea` | Gemini chain | Input: only the founder's text. Output schema is strict; no market "facts". |
| `generate_icps` | Gemini chain | Input: idea + hypothesis. Scores are explicitly hypotheses. |

Prompts must forbid stating market facts. The model may only rephrase the founder's input and
propose assumptions and questions.

## UI

- "New idea" page with the intake form.
- Idea page sections: Hypothesis, Unknowns (research plan), ICPs, each with an "AI assumption"
  badge, edit controls and an analysis progress state.

## Acceptance criteria

- [ ] A new idea produces a hypothesis, at least 3 unknowns and at least 1 ICP in one action.
- [ ] Every generated item is visibly labelled as an AI assumption; nothing is labelled "fact".
- [ ] The user can edit, add, delete and re-generate each item, and edits persist.
- [ ] Analysis runs in the worker; the HTTP request returns immediately and progress is visible.
- [ ] If Gemini is down, the router falls back to local, or shows a clear error state. No crash.
- [ ] Tests cover the services, the job, prompt and schema validation (FakeProvider) and the API.

## Decisions (2026-11-01)

1. **Hypothesis history: keep versions (append-only).** Every edit or re-generation inserts a
   new `hypotheses` row with `version + 1`, and the highest version is current.
   - **Why:** PRD §28 experiments exist to change the hypothesis ("update ICP"), and the Phase 4
     report should show how the idea evolved and why. An append-only insert costs about the same
     as an update and loses nothing.
   - **Not versioned:** unknowns and ICPs. They use status fields instead, to keep 1A small.
2. **ICP score: a fixed rubric, totalled in code.** The model rates each criterion 1–5 with a
   one-line rationale. The weighted 0–100 total is computed deterministically.
   - **Why:** LLM-picked numbers aren't calibrated or comparable across ideas or runs. A rubric
     makes the score explainable, consistent with PRD §16 and §24, and lets Phase 1B evidence
     later adjust individual criteria.
   - **The score is still an assumption** until evidence exists, and is labelled that way.

   | Criterion | Weight | Question the model answers (1–5) |
   |---|---|---|
   | Pain likelihood | 30 | How likely is this segment to feel the problem strongly? |
   | Ability to pay | 25 | Does this segment plausibly have budget and buying authority? |
   | Reachability | 20 | Can these companies and roles be found and contacted from public info? |
   | Frequency / urgency | 15 | How often, or how urgently, does the problem occur for them? |
   | Segment size | 10 | Are there enough such companies in the target market? |

   `score = Σ weight × (rating − 1) / 4`, so all 1s give 0 and all 5s give 100.
