# Phase 1A — Idea intake & analyzer

- **Status:** Done (2026-11-01)
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

## Kickoff plan (concrete design)

- **Module:** `app/modules/analysis/` (models, schemas, prompts, rubric, service, router). The job
  lives in `app/workers/jobs.py` and calls the service.
- **Runs:** `analysis_runs.kind` is `full` (hypothesis + unknowns + ICPs) or `icps` (ICPs only,
  regenerated from the current hypothesis). Status is `queued → running → succeeded | failed`,
  and `step` (`hypothesis` / `icps`) shows progress. Only one active run per idea; starting
  another returns 409.
- **Re-generation never destroys user work:**
  - a new hypothesis version is appended;
  - open AI-sourced unknowns become `dropped`, and active AI-sourced ICPs become `dismissed`;
  - anything the user created or edited (`source = user`) is kept.
- **Editing** an AI item switches its `source` to `user`. Removing an item sets its status
  (unknown → `dropped`, ICP → `dismissed`); nothing is hard-deleted.
- **Labels:** all 1A items are assumptions. The UI shows "Assumption · AI" or
  "Assumption · edited by you".
- **Prompts:** they state that the model has no market data and must not output statistics,
  company names or market facts. They only structure the founder's input and propose testable
  assumptions and neutral questions.
- **Queue:** the API opens an arq pool in its lifespan; a `get_queue` dependency is overridden in
  tests. A failed enqueue marks the run failed and returns 503.

## Out of scope

Web research and evidence (1B), competitors (1C), companies and prospects (1D).

## Data model

| Table | Key columns |
|---|---|
| `hypotheses` | idea_id, version (unique per idea), problem, users, buyer, decision_maker, economic_value, geography, industry, source (`ai` / `user`), change_note? — append-only |
| `unknowns` | idea_id, question, category, priority, status (`open` / `answered` / `dropped`), source |
| `icps` | idea_id, name, company_type, size_min, size_max, geography, signals (json), roles (json), score_components (json: criterion, rating 1–5, rationale), hypothesis_score (computed), source, is_primary, status (`active` / `dismissed`) |
| `analysis_runs` | idea_id, kind (`full` / `icps`), status, step, error, started_at, finished_at |

## API (as built)

All routes are nested under `/ideas/{idea_id}`, so ownership is checked in one place.

- `GET /analysis`: current hypothesis, unknowns, active ICPs and the latest run, in one call.
- `POST /analyze` (full run) and `POST /icps/generate` (ICPs only). Both return 202 with the run.
  An active run gives 409, and an unreachable queue gives 503.
- `GET /analysis-runs/{run_id}`.
- `GET /hypothesis/versions`, and `POST /hypothesis` (an edit saved as a new version).
- `GET/POST /unknowns` (`?include_dropped=true`), `PATCH /unknowns/{id}`. Removing an unknown
  is `status=dropped`.
- `GET/POST /icps` (`?include_dismissed=true`), `PATCH /icps/{id}`. Removing an ICP is
  `status=dismissed`. Every ICP response includes `score_breakdown`.

## Jobs

`run_analysis(run_id)` in `app/workers/jobs.py` calls `analysis.service.execute_run`. Each
finished step is committed. If the job itself crashes, the run is marked failed so it doesn't
block the idea.

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

- [x] A new idea produces a hypothesis, at least 3 unknowns and at least 1 ICP in one action.
      Live: "Create idea" with "Analyze right away" gave 5–6 unknowns and 3 ICPs.
- [x] Every generated item is visibly labelled as an AI assumption; nothing is labelled "fact".
      Browser check: 9 "Assumption · AI" badges, 0 "fact" labels.
- [x] The user can edit, add, remove and re-generate each item, and edits persist. Browser
      check: hypothesis v2 with a note, an unknown added and marked answered, the primary ICP
      switched, history shown. Removing sets a status instead of deleting (kickoff decision).
- [x] Analysis runs in the worker; the HTTP request returns immediately (202) and progress is
      visible (status banner with the current step, polled every 2.5s).
- [x] If Gemini is down, the router falls back to local. Live: with `GEMINI_API_KEY=""` the ICPs
      were generated by `qwen2.5:7b`. A failed run shows an error banner with "Try again".
- [x] Tests cover the services, the job, prompt and schema validation (FakeProvider) and the API:
      66 tests, CI green.

## Notes carried forward

- **Gemini availability:** during this phase, `3.8-flash` timed out repeatedly and `3.6-flash`
  returned 503 "high demand", while `2.5-flash` answered. The chain and cooldown handled it; a
  full analysis took about 50–70s. Consider putting `2.5-flash` earlier in `GEMINI_MODELS` if this
  persists.
- **Local fallback quality:** qwen's ICPs are usable but weaker (e.g. "Government Construction
  Projects" isn't a company profile). Keep synthesis tasks on Gemini.
- **Bugs found by the live end-to-end run, now fixed with regression tests:**
  - the worker didn't register every ORM model;
  - a crashed job left its run stuck in "queued".
  Keep doing a live run per phase, because unit tests import everything and hide this class of
  bug.
- Browser checks run with Playwright driving the installed Chrome, from the scratchpad, since the
  Chrome extension isn't connected.

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
