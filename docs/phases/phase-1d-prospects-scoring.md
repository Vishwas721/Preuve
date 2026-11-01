# Phase 1D — Prospect discovery, enrichment & scoring

- **Status:** Not started (draft)
- **Goal:** Find companies that match the ICP and are likely to have the problem, identify
  relevant roles, and rank prospects with an explainable score.
- **PRD refs:** §14 Prospect discovery, §15 Enrichment, §16 Lead scoring, §37 privacy

## Scope

- **Company discovery (ADR 0004):** the `/research-idea` skill gains a prospecting step driven by
  the primary ICP (industry, geography, size signals), public directories and companies already
  in the evidence. The research pack gains a `companies[]` section. Preuve verifies each company
  site (it fetches the page and checks the cited facts) before storing it.
- **Enrichment** from each company's public website: industry, location, services, size
  estimate (with the signal used, e.g. "careers page lists 40 openings"), technology hints,
  relevant public evidence.
- **Relevant roles:** the role titles to target, from the ICP (owner, operations director, PM,
  ...).
- **Contacts:** only from public professional sources (the company website's team or about
  pages). Minimal fields: name, role, public business email or contact page, source URL.
  Nothing sensitive. Every contact keeps its provenance.
- **Lead score (PRD §16 weights):**
  - company fit 20, problem evidence 25, role relevance 20, size 10, geography 5, technology
    fit 10, other signals 10;
  - each component is stored with points and a written reason that links to evidence;
  - deterministic rules first; the LLM only helps judge fit from extracted fields.
- **Target:** 20+ prospects for one idea.

## Out of scope

Sending anything (Phase 2). Paid enrichment APIs. Guessing email patterns (e.g.
first.last@domain): no unverified personal emails.

## Data model (draft)

| Table | Key columns |
|---|---|
| `companies` | idea_id, name, domain, location, industry, size_estimate, size_signal, technologies (json), services (json), source_url |
| `contacts` | company_id, name, role, email?, contact_url?, source_url, collected_at |
| `prospects` | idea_id, company_id, contact_id?, icp_id, status (`new` / `shortlisted` / `excluded`) |
| `lead_scores` | prospect_id, total, components (json: name, points, max, reason, evidence_ids), scored_at |
| `company_evidence` | company_id, evidence_id |

## API (draft)

- `POST /ideas/{id}/prospects/discover` (job) and `GET /ideas/{id}/prospects` (filters + sort).
- `GET /prospects/{id}` (score breakdown) and `PATCH /prospects/{id}` (status).
- `DELETE /contacts/{id}`, which also covers deletion requests (PRD §37).

## Jobs

`prospect_discovery_job(idea_id, icp_id)`: discover → dedupe by domain → enrich → contacts →
score.

## LLM tasks

| Task | Provider | Notes |
|---|---|---|
| `extract_fields` | local | Company page → structured company profile and team entries. |
| `classify_evidence` | local | Does this company show signs of the problem? |

## UI

Minimal prospect list with score, filters and a score breakdown drawer (polished in 1E).

## Acceptance criteria

- [ ] At least 20 prospects for one real idea, deduplicated by domain.
- [ ] Every score shows each component's points, a reason, and linked evidence where relevant.
- [ ] Every contact has a source URL; no contact data comes from non-public sources.
- [ ] Re-scoring the same data gives the same result (deterministic rules, tested).

## Open questions (settle at kickoff)

- Which free public directories are allowed (check each one's terms and robots.txt)?
- How should company size be estimated without paid data (careers pages, about pages)?
