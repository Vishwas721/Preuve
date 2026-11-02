# Phase 1D — Prospect discovery, enrichment & scoring

- **Status:** In progress (kickoff 2026-11-02)
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

## Kickoff plan (concrete design, ADR 0004)

- **Same pipeline as 1B and 1C.** Companies and contacts arrive in the research pack (schema
  1.2), Preuve verifies them, and scores are computed in code. There's no crawler job and no LLM
  call. The draft's `prospect_discovery_job` and `extract_fields` / `classify_evidence` tasks are
  dropped.
- **A prospect is a company within an idea.** Companies are already idea-scoped, so there's no
  separate `prospects` table: status and target ICP live on `companies`. Phase 2 outreach
  targets a `contact`.
- **Pack `companies[]`:**
  - `ref`, `name`, `website`, `location?`, `industry?`, `description`;
  - `size_estimate? {min?, max?, signal, evidence_ref}`;
  - `in_target_geography? {value, evidence_ref}`;
  - `technologies[]`;
  - `evidence_refs[]` (at least 1: the company's own pages, job postings, news);
  - `assessments` for `company_fit`, `technology_fit` and `other_signals`, each
    `{rating 0–5, rationale, evidence_refs}`;
  - `contacts[]`, each `{name, role, email?, evidence_ref}`.
- **Verification:**
  - **company:** stored only if at least one cited evidence item is stored. Deduplicated by
    domain within the idea; re-imports merge, and user status changes are kept.
  - **contact:** stored only if its `evidence_ref` is **verified** *and* the person's name appears
    in that verified quote. Unverifiable pages are never a source of personal data.
  - **email:** kept only if the address appears verbatim on the fetched page. It's never guessed
    (`first.last@` patterns are forbidden).
  - assessment refs that weren't stored are removed. An assessment left with no evidence scores
    0 (no evidence means no points).
- **Lead score (PRD §16), deterministic code in `prospects/scoring.py`.** Every component stores
  points, max, a reason and evidence ids.

  | Component | Max | Rule |
  |---|---|---|
  | Company fit | 20 | `20 × rating / 5` from the assessment; 0 without stored evidence |
  | Problem evidence | 25 | Linked evidence with stance `supports`: verified counts 1, unverifiable 0.5. 0 → 0, 0.5 → 8, 1 → 15, 2+ → 25 |
  | Role relevance | 20 | Best contact role vs the ICP's roles (all significant words of an ICP role appear in the contact's role): buyer 20, user 12, other contact 5, none 0 |
  | Company size | 10 | Estimate within the ICP size band 10, overlapping 5, outside or unknown 0 |
  | Geography | 5 | `in_target_geography = true` with a stored evidence ref 5, else 0 |
  | Technology fit | 10 | `10 × rating / 5`; 0 without stored evidence |
  | Other signals | 10 | `10 × rating / 5`; 0 without stored evidence |

  The score uses the company's ICP (default: the idea's primary ICP at import time). Re-scoring
  recomputes from stored inputs only. An `inputs_hash` proves the same inputs give the same
  score.
- **Privacy (PRD §37):**
  - contacts are only people named on the company's own public pages (team, leadership,
    contact); minimal fields;
  - **no** LinkedIn, people-search or data-broker sites, no personal emails or phones, and
    nothing beyond professional role;
  - `DELETE /contacts/{id}` hard-deletes a person. Phase 2 must add a suppression entry on
    deletion.
- **The `/research-idea` skill moves to method v3,** adding step 5c (prospecting): a target of
  20+ companies for the chosen ICP, sourced from public directories and the companies' own
  sites.

## Decisions (2026-11-02)

- **Allowed sources for companies:**
  - the companies' own websites;
  - public association or member directories and public lists, when robots.txt allows Preuve to
    fetch them (it's checked on import);
  - news and job postings.
- **Not allowed:** LinkedIn, ZoomInfo / Apollo / people-search or data-broker sites, or any page
  that requires login.
- **Company size without paid data:** the company's own stated headcount ("over 200
  employees"), counts on its careers or team page, or association listings. Otherwise
  **unknown**, which scores 0 for size. That's honest rather than guessed.

## Data model

| Table | Key columns |
|---|---|
| `companies` | idea_id, icp_id?, name, domain (unique per idea), website, location?, industry?, description, size_min?, size_max?, size_signal?, size_evidence_id?, in_geo?, geo_evidence_id?, technologies (json), assessments (json, refs resolved to evidence ids), status (`new` / `shortlisted` / `excluded`), last_import_id? |
| `company_evidence` | company_id, evidence_id |
| `contacts` | company_id, name, role, email?, evidence_id (the verified quote naming them), source_url, collected_at |
| `lead_scores` | company_id, total, components (json), inputs_hash, icp_id?, scored_at (the latest is current) |

## API

All routes are under `/ideas/{idea_id}`:

- `GET /prospects` (filters: status, min_score; sorted by score) and `GET /prospects/{company_id}`
  (contacts, score breakdown, evidence ids).
- `PATCH /prospects/{company_id}` (status, icp_id).
- `POST /prospects/rescore` (synchronous: recomputes from stored data, e.g. after changing the
  primary ICP).
- `DELETE /contacts/{contact_id}`.

## UI

A minimal "Prospects" section on the idea page:

- a table sorted by score, with status and minimum-score filters;
- an expandable row with the score breakdown (points, reasons, evidence links), contacts with
  their source and a delete control, and a status selector.

Polish comes in 1E.

## Acceptance criteria

- [ ] At least 20 prospects for one real idea, deduplicated by domain.
- [ ] Contacts are stored only when their name is in a verified quote; emails only when present
      on the page (tested).
- [ ] Every score shows each component's points, a reason, and linked evidence where relevant.
- [ ] Every contact has a source URL; no contact data comes from non-public sources.
- [ ] Re-scoring the same data gives the same result (deterministic rules, tested).
