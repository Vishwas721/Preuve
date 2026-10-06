# Preuve — Roadmap

Work proceeds in small phases. **Each phase:**

1. starts with a short plan for that phase only (scope, tables, endpoints, UI);
2. is built in small commits, each pushed to `main`;
3. ends with its acceptance criteria verified and a review stop before the next phase.

Nothing from a later phase is built early. Status: `[ ]` todo · `[~]` in progress · `[x]` done.

---

## Phase 0 — Foundation `[~]`

Monorepo, infra, API skeleton, DB + migrations, worker queue, hybrid LLM layer, search layer, web
skeleton, CI, docs.

**Acceptance**
- `docker compose up` brings up Postgres, Redis, SearXNG healthy.
- `GET /health` reports db, redis, ollama status.
- Ideas CRUD round-trips through Postgres.
- LLM router validates output and escalates local → Gemini on failure (tested with fakes).
- Claim guardrail rejects facts without evidence ids.
- Web dashboard shows API health and ideas list.
- CI green (ruff, pytest, web lint + build).

---

## Phase 1A — Idea intake & analyzer `[ ]`

- Idea form (idea, target market, why it matters, optional fields from PRD §8).
- `analyze_idea` → structured hypothesis (problem, users, buyer, economic value, geography,
  industry) + **unknowns** (the research plan). Everything stored as `assumption` claims.
- `generate_icps` → 1–3 candidate ICPs with hypothesis score + rationale.
- Tables: `hypotheses`, `unknowns`, `icps`.

**Acceptance:** a new idea produces a hypothesis, ≥3 unknowns, ≥1 ICP; all are visibly labelled
as AI assumptions; user can edit them.

## Phase 1B — Research & evidence engine `[ ]`

- `POST /ideas/{id}/research` creates a `research_run` and enqueues a job; progress is pollable.
- Queries are generated from unknowns + ICP; SearXNG search → fetch → `extract_fields` /
  `classify_evidence` per page.
- Tables: `research_runs`, `sources`, `evidence` (type, quote, fact/inference/assumption,
  relevance, confidence, company, linked hypothesis/unknown).

**Acceptance:** a run on a real idea yields evidence items, each with a URL and verbatim quote;
items with no source are impossible to store; "No evidence found" shown when empty.

## Phase 1C — Competitors & alternatives `[ ]`

- `analyze_competitors` over collected sources: direct, indirect, manual, service alternatives.
- Table: `competitors` (kind, name, url, evidence ids).

**Acceptance:** the idea page answers "how is this solved today?" with sourced entries only.

## Phase 1D — Prospect discovery, enrichment & scoring `[ ]`

- Company discovery from ICP via search; enrichment from company websites (industry, size
  estimate, location, services, public evidence, relevant roles).
- Contacts only from public professional sources, minimal fields, always with source.
- Explainable lead score using PRD §16 weights; every point has a reason.
- Tables: `companies`, `contacts`, `prospects`, `lead_scores`.

**Acceptance:** 20+ prospects for one idea, each with score breakdown and reasons.

## Phase 1E — Phase 1 UI `[ ]`

- Portfolio dashboard (PRD §27/§38), idea detail (§39), research explorer (§40), prospect
  explorer with filters (§41), research progress view.

**Acceptance:** PRD §46 items 1–6 visible in the UI for one fresh idea.

---

## Phase 2 — Outreach `[ ]`

- `draft_outreach` produces research-oriented drafts (PRD §17) citing evidence.
- Approval gate: `DRAFT → APPROVED | REJECTED`; only approved can send (PRD §18).
- `EmailProvider` interface; first implementation: SMTP (e.g. Gmail app password).
- Safety (PRD §36): daily limits, suppression list, unsubscribe link + handling, duplicate &
  frequency checks, bounce tracking, transparent sender identity.
- Tables: `outreach_campaigns`, `messages`, `suppressions`.

**Acceptance:** cannot send an unapproved message; suppressed addresses are never contacted;
limits enforced in tests.

## Phase 3 — Responses & interviews `[ ]`

- Response ingestion: manual paste first, then IMAP polling.
- Response intelligence (PRD §20) and conversation intelligence (§21).
- Interview workspace: guides generated from open unknowns (§22), notes, WTP records (§23).
- Tables: `responses`, `interviews`, `interview_notes`, `wtp_signals`.

**Acceptance:** a pasted reply becomes a structured record that becomes evidence of kind `fact`
linked to the response.

## Phase 4 — Validation & decision `[ ]`

- Weighted validation score (PRD §24) computed from stored evidence only.
- Validation states (§25), decision engine with strong/weak evidence and next action (§26).
- Experiments (§28), validation report (§44), portfolio comparison (§27).
- Tables: `validation_scores`, `experiments`.

**Acceptance:** score is fully reproducible from DB data; every recommendation lists the evidence
behind it; a weak idea gets told "don't build yet".

## Phase 5 — Hardening `[ ]`

- Real auth, multi-user, teams.
- Data deletion & export, provenance audit, privacy review (PRD §37).
- Deployment.
