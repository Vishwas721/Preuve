# Phase 1B — Research import & evidence verification

- **Status:** In progress (kickoff 2026-11-01; rewritten for [ADR 0004](../adr/0004-claude-code-research-analyst.md))
- **Goal:** Get high-quality public evidence for or against an idea by having Claude Code do the
  research. Preuve imports the result, **independently verifies every quote against the live
  page**, and stores the evidence with full provenance and an honest label.
- **PRD refs:** §11 Market research, §12 Evidence engine, §35 guardrails, §37 privacy

## How it works

```
You paste an idea into Claude Code
        │  /research-idea  (fixed method, versioned)
        ▼
research/<idea-slug>/pack.json   +   research/<idea-slug>/report.md
        │  uv run python -m app.scripts.import_research research/<idea-slug>/pack.json
        ▼
POST /ideas/{id}/research-imports   ──►  arq job: verify each evidence item
        │                                  fetch URL (robots.txt respected)
        │                                  find the verbatim quote on the page
        ▼
evidence (verified | unverifiable)  +  import report (rejected items and why)
        ▼
Idea page: evidence list with quotes, sources and labels; unknowns show their findings
```

## Scope

### 1. Research pack (the contract)

- Defined as Pydantic models in `app/modules/research/pack.py`. These are the source of truth.
- Exported to `docs/research-pack.schema.json` by a script; a test fails if the export is stale.
- **`meta`:**
  - `schema_version`, `method_version`, `idea_id`, `researcher` (`claude-code`);
  - `started_at`, `finished_at`;
  - `queries` (what was searched, for transparency), `notes`.
- **`evidence[]`** fields:
  - `ref` (pack-local id, e.g. `ev-01`), `url`, `title`;
  - `source_type`: `job_posting` / `forum` / `review` / `news` / `industry_publication` /
    `company_site` / `report` / `directory` / `other`;
  - `published_at?`;
  - `quote`: copied **verbatim** from the page, max ~500 characters;
  - `statement`: what the quote shows, in one sentence;
  - `kind`: `fact` or `inference` (assumptions are not evidence);
  - `stance`: `supports` / `contradicts` / `neutral`, relative to the hypothesis;
  - `relevance`: `high` / `medium` / `low`;
  - `unknown_ids[]`: which unknowns it informs;
  - `company_name?`.
- **`unknown_findings[]`:**
  - `unknown_id`;
  - `status`: `answered` / `partially_answered` / `no_evidence_found`;
  - `summary`: a list of `Claim`s citing evidence `ref`s.
- **`hypothesis_update?`** (optional): proposed new hypothesis fields, with a `rationale` that
  cites evidence refs. Imported as a **new hypothesis version** with source `research`, never
  applied silently.
- **`new_unknowns[]`** (optional): questions the research raised. Imported with source
  `research`.

### 2. Import and verification

- `POST /ideas/{id}/research-imports` validates the pack (schema, idea id, ref uniqueness,
  citation refs exist) and returns 422 with a clear error list if it's invalid. Otherwise it
  stores the import and enqueues `verify_research_import`.
- **Verification, per evidence item:**
  - fetch with `PageFetcher` (robots.txt respected, timeout, provenance recorded);
  - normalize the page text and the quote (case, whitespace, curly quotes, dashes, ellipses)
    and look for the quote. If the main-content extraction misses it, fall back to the full
    page text;
  - **verified:** the quote was found. Stored with `fetched_at` and a content hash.
  - **unverifiable:** the page couldn't be fetched (robots.txt, 4xx/5xx, paywall). Stored but
    flagged, shown separately, and excluded from scoring by default.
  - **rejected:** the page was fetched but the quote isn't on it. **Not stored as evidence**;
    listed in the import report.
- **Claims** in `unknown_findings` and `hypothesis_update` must cite only refs of stored
  (verified or unverifiable) evidence (`verify_citations`). A claim citing a rejected item is
  dropped and reported.
- Bounded concurrency and a per-domain politeness delay.
- **Re-importing** a pack for the same idea adds a new import. Evidence is deduplicated by URL
  plus normalized quote.

### 3. The `/research-idea` skill (`.claude/skills/research-idea/SKILL.md`)

- **Inputs:** an idea, either pasted text or an existing idea id. If it's new, the skill creates
  it via the API and runs the 1A analysis, so research targets the unknowns.
- **Fixed method (v1):**
  1. Read the idea, the current hypothesis, the open unknowns and the primary ICP from the API.
  2. Plan queries per unknown, covering the PRD §11 source types: job postings (manual
     workflows), forums and communities, reviews of existing tools (complaints), industry
     publications, news, company sites.
  3. Search, open the pages that look promising, and copy quotes **verbatim**.
  4. **Actively look for contradicting evidence** (e.g. "this is solved", "not a problem").
  5. For each unknown: answered, partially answered, or **no evidence found**.
  6. Write `pack.json` (validated against the schema) and `report.md` (a readable summary that
     cites the same refs).
  7. Run the import script and summarize the verification results.
- **Rules:**
  - never paraphrase inside `quote`;
  - never cite a page that wasn't opened;
  - no personal data beyond what the evidence needs: no usernames, no private individuals'
    names. A company name is fine.
  - Stop at the configured budget (default: about 15–25 evidence items, at least 2 contradiction
    searches).
- Packs and reports are committed under `research/<idea-slug>/`, which keeps the research
  history versioned.

### 4. UI

- **Idea page, new "Evidence" section:**
  - items grouped by stance;
  - quote, source link, source type, kind (fact / inference), relevance, verification badge;
  - unverifiable items in a collapsed group;
  - "No evidence found." when the list is empty.
- **Unknowns** show their latest finding status and summary, with links to the cited evidence.
- **Import history:** date, method version, counts (verified / unverifiable / rejected), and a
  link to the rejected items with reasons.
- A **"research" source badge** on hypothesis versions and unknowns that came from a pack.

## Out of scope

- The automated crawler (deferred, ADR 0004).
- Competitors (1C) and companies (1D). Those phases **extend the research pack** with
  `competitors[]` and `companies[]` sections, and add steps to the skill.
- Full research explorer polish (1E).

## Data model (draft)

| Table | Key columns |
|---|---|
| `research_imports` | idea_id, schema_version, method_version, researcher, pack (json), status (`queued` / `verifying` / `done` / `failed`), report (json: counts, rejected items, dropped claims), error |
| `sources` | idea_id, url, final_url, title, fetched_at, fetch_status, content_hash, text |
| `evidence` | idea_id, import_id, source_id, ref, quote, statement, source_type, kind, stance, relevance, company_name?, published_at?, verification (`verified` / `unverifiable`), verification_note, dismissed |
| `evidence_unknowns` | evidence_id, unknown_id |
| `unknown_findings` | unknown_id, import_id, status, summary (json claims with evidence ids) |

`Source` gains a value, `research` (hypotheses, unknowns).

## API (draft)

All routes are under `/ideas/{idea_id}`:

- `POST /research-imports` (202, or 422 with validation errors), `GET /research-imports`,
  `GET /research-imports/{id}`.
- `GET /evidence` (filters: stance, kind, verification, unknown) and `PATCH /evidence/{id}`
  (dismiss, or relabel kind or stance; changes are recorded).
- `GET /analysis` also returns the latest findings per unknown.

## Jobs

`verify_research_import(import_id)`: fetch, find quotes, store evidence, check claims, apply the
optional hypothesis update and new unknowns, write the report. Crash safety works as in 1A: the
import is marked failed and never left stuck.

## LLM tasks

None required. Verification is deterministic. Local models may be used later for relabel
suggestions; not in this phase.

## Acceptance criteria

- [ ] The pack schema is exported to `docs/research-pack.schema.json`; a test keeps it in sync.
- [ ] An invalid pack is rejected with a precise error list (bad refs, unknown ids, missing
      quote, etc.).
- [ ] An evidence item whose quote isn't on its page is rejected and reported (tested with
      mocked HTTP).
- [ ] An item whose page blocks fetching is stored as `unverifiable` and shown separately.
- [ ] Claims citing rejected or unknown refs are dropped and reported (`verify_citations`).
- [ ] A hypothesis update from research becomes a new version with source `research`; nothing
      the user wrote is overwritten.
- [ ] **Live:** `/research-idea` on a real idea produces a pack. Importing it gives mostly
      verified evidence, shown on the idea page with working source links. Unknowns show
      findings, including "No evidence found" where honest.
- [ ] Tests cover the schema, verification and matching rules, import service, job and API.

## Decisions (2026-11-01)

- **Reddit:** no special integration. Reddit blocks crawlers, so Reddit items can be cited but
  will import as `unverifiable`. That's honest and visible.
- **Stored page text:** keep the full extracted text per source. It allows re-verification and
  audit. Revisit retention in Phase 5.
- **Other free sources:** none needed. The skill decides where to look; verification only needs
  public URLs.

## Kickoff plan (concrete design)

- **Quote matching (decided):** an exact match after normalization. Normalization covers Unicode
  NFKC, lowercasing, curly quotes to straight, every dash to `-`, removing zero-width
  characters, and collapsing whitespace. `…`, `...` and `[...]` split a quote into fragments
  that must all be found **in order**. Each fragment must be at least 8 characters, and the
  whole quote at least 20. The main extracted text is tried first, then the full page text.
- **Module:** `app/modules/research/`:
  - `pack.py` (the contract), `matching.py`, `models.py`, `schemas.py`, `service.py`,
    `router.py`;
  - the job `verify_research_import` lives in `app/workers/jobs.py`;
  - the analysis module exposes `add_hypothesis_version` / `add_unknown` for research to call.
- **One CLI for the skill**, `app/scripts/research.py`:
  - `context <idea_id>`: the idea, current hypothesis, unknowns with ids, and primary ICP, as
    JSON;
  - `create`: create an idea, optionally analyzing it;
  - `fetch <url>`: prints the **exact text Preuve will verify against**, so quotes are copied
    from it rather than from a summarizing tool;
  - `validate <pack>`: local schema check;
  - `import <pack>`: POST it, wait, print the verification report.
- **Read model:** `GET /ideas/{id}/research` returns evidence, the latest finding per unknown,
  and the import history in one call. `/analysis` is unchanged, which keeps the modules
  decoupled.
- **Unknown status is not changed automatically.** A finding is shown next to the unknown, and
  the user decides whether it's answered.
- **Honest downgrade:** if every claim in a finding is dropped during verification, its status
  becomes `no_evidence_found`, and the report says why.
- **Evidence edits:** dismissing or relabelling sets `user_edited` and keeps the original labels.
- `analysis.Source` gains `research`. The enum isn't native, so no migration is needed for the
  new value.
