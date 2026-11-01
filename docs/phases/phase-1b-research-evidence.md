# Phase 1B — Research & evidence engine

- **Status:** Not started (draft)
- **Goal:** Gather public evidence for or against the hypothesis, and store each item with full
  provenance and an honest fact / inference / assumption label.
- **PRD refs:** §11 Market research engine, §12 Evidence engine, §31 async architecture,
  §35 guardrails, §37 privacy

## Scope

- **Research run:** `POST /ideas/{id}/research` creates a `research_run` and enqueues a job.
  Progress (queries done, pages fetched, evidence found) can be polled.
- **Query planning:** build search queries from the open unknowns, the hypothesis and the primary
  ICP. Templates first; the LLM only helps expand them. Targets PRD §11 evidence types: job
  postings, forums, reviews, industry publications, news, company sites.
- **Search → fetch → extract** for each result:
  - SearXNG search;
  - `PageFetcher.fetch` (robots.txt respected);
  - store a `source` (url, title, fetched_at, content hash);
  - `extract_fields` / `classify_evidence` (local) pull **verbatim quotes**, their relevance and
    the linked unknown or hypothesis.
- **Evidence record (PRD §12):** source, url, company (if any), date, evidence type, verbatim
  quote, statement, kind (fact / inference / assumption), relevance, confidence, linked
  hypothesis or unknown.
- **Integrity checks, enforced in code:**
  - a quote must appear in the stored page text (exact or normalized match), otherwise it is
    rejected;
  - an evidence row cannot exist without a source;
  - a run that finds nothing records and shows "No evidence found."
- **Dedup:** the same URL or content hash is not stored twice per idea.
- **Politeness:** per-domain rate limit, concurrency cap, timeouts.

## Out of scope

Competitor synthesis (1C), company discovery (1D), Phase 1 explorer UI polish (1E). This phase
ships a minimal evidence list only.

## Data model (draft)

| Table | Key columns |
|---|---|
| `research_runs` | idea_id, status, queries (json), stats (json), error, started_at, finished_at |
| `sources` | idea_id, url, final_url, title, fetched_at, content_hash, text (or a pointer to it), source_type |
| `evidence` | idea_id, source_id, research_run_id, unknown_id?, hypothesis_id?, evidence_type, quote, statement, kind, relevance, confidence, company_name?, published_at? |

## API (draft)

- `POST /ideas/{id}/research` and `GET /ideas/{id}/research-runs/{run_id}`.
- `GET /ideas/{id}/evidence` (filters: type, kind, relevance, unknown).
- `PATCH /evidence/{id}`: the user can relabel or dismiss an item. Dismissed items stay for audit.

## Jobs

`research_job(run_id)`: plan queries → search → fetch (bounded concurrency) → extract and
classify → verify quotes → store → update stats.

## LLM tasks

| Task | Provider | Notes |
|---|---|---|
| `extract_fields` | local (qwen2.5:7b) | Single page → candidate quotes + fields. Precise field definitions. |
| `classify_evidence` | local | Snippet + hypothesis → relevance / supports / kind. |
| `synthesize_evidence` | Gemini chain | Optional run summary; claims must pass `verify_citations`. |

## UI

Minimal: a "Run research" button, a progress indicator, and an evidence list with quote, source
link, type, kind and relevance badges.

## Acceptance criteria

- [ ] A run on a real idea produces evidence items, each with a URL, fetched_at time and a
      verbatim quote that is present in the stored page.
- [ ] Storing evidence without a source, or with a quote not found in the source, is impossible
      (tested).
- [ ] An empty run shows "No evidence found."
- [ ] robots.txt and the rate limits are respected (tested with mocked HTTP).
- [ ] Runs are resumable or fail cleanly; progress stats are accurate.

## Open questions (settle at kickoff)

- **Reddit:** use the official Reddit API (needs an app and credentials, and its terms), or skip
  Reddit? The robots.txt check currently blocks crawling it.
- How much page text should we store (the full text, or a trimmed window around the quotes)?
- Do we need other free sources (e.g. public job boards with APIs)?
