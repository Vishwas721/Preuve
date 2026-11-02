# Phase 1C — Competitors & alternatives

- **Status:** Done (2026-11-02)
- **Goal:** Answer "how is this problem solved today?" with sourced entries only.
- **PRD refs:** §13 Competitor & alternative analysis, §35 guardrails

## Scope

- **Discovery (ADR 0004):** the `/research-idea` skill gains a competitor step (targeted searches
  such as "<problem> software", "<problem> template", "<problem> consultant", the founder's known
  competitors, and mentions in existing evidence). The research pack gains a `competitors[]`
  section, and each entry cites verified evidence refs.
- **Classification** into four kinds:
  - **direct**: products solving the same problem;
  - **indirect**: different software solving part of it;
  - **manual**: Excel, Sheets, email, paper, WhatsApp, internal tools;
  - **service**: consultants, agencies, freelancers.
- **Each entry** has: name, url, kind, what it covers, pricing if publicly stated, the evidence
  ids that mention it, and how customers talk about it (praise or complaints) when the sources
  say so.
- **"Current solutions" summary:** written by the researcher in the pack as claims citing
  evidence refs, and verified like 1B findings. Claims citing rejected evidence are dropped;
  with nothing left, the UI shows "No evidence found."

## Out of scope

Pricing strategy and positioning advice. Feature-by-feature comparison matrices.

## Kickoff plan (concrete design, ADR 0004)

- **No new crawler and no LLM.** Competitors arrive in the research pack and are verified by the
  1B pipeline. The `analyze_competitors` / `extract_fields` tasks from the draft are dropped for
  this phase; the researcher writes the synthesis, and Preuve verifies its citations.
- **Pack schema 1.1** (backward compatible: 1.0 packs still import):
  - `competitors[]`, each with `ref` (`comp-01`), `name`, `url?` (null for generic alternatives
    like spreadsheets), `kind` (`direct` / `indirect` / `manual` / `service`), `description`
    (what it covers), `pricing_note?` (only if publicly stated, with an evidence ref),
    `evidence_refs[]` (at least 1), and `sentiment[]` (claims about praise or complaints,
    citing refs);
  - `current_solutions[]`: claims summarizing how the problem is solved today.
- **Verification rules:**
  - a competitor is stored only if at least one cited evidence item survives (verified or
    unverifiable); otherwise it's rejected and reported;
  - a competitor whose surviving evidence is all unverifiable is flagged in the UI;
  - sentiment and summary claims citing rejected refs are dropped, the same as 1B findings.
- **Re-imports merge by normalized name per idea:** evidence links are added, and research text
  is refreshed. If the user edited an entry, their text is kept and only evidence links are
  added. Dismissed entries stay dismissed.
- **The current-solutions summary** is stored per import (`research_imports.solutions_summary`);
  the latest non-empty one is shown.
- **The `/research-idea` skill moves to method v2,** adding a competitors and alternatives step:
  - the founder's known competitors, direct and indirect products, manual workarounds and
    service providers;
  - at least one search for complaints about the leading tools.
- **Settled open question:** founder-listed competitors are verified through the skill. The skill
  must research each one and include it if public evidence exists; otherwise the report says no
  evidence was found. There's no separate auto-fetch machinery.

## Data model

| Table | Key columns |
|---|---|
| `competitors` | idea_id, name, name_key (normalized, unique per idea), url?, kind, description, pricing_note?, sentiment (json claims), source (`research` / `user`), status (`active` / `dismissed`), user_edited, last_import_id? |
| `competitor_evidence` | competitor_id, evidence_id |
| `research_imports` | + `solutions_summary` (json claims, evidence ids) |

## API

All routes are under `/ideas/{idea_id}`:

- `GET /competitors` (`?include_dismissed=true`), `POST /competitors` (manual add, source
  `user`), `PATCH /competitors/{id}` (edit or dismiss; edits set `user_edited`).
- `GET /research` also returns `competitors` and `current_solutions` (the latest summary).

## UI

A "How it's solved today" section on the idea page:

- the summary first (claims with citation links);
- then entries grouped by kind (Direct / Indirect / Manual workarounds / Services);
- each entry shows its description, pricing note, what customers say, linked evidence, and
  source badges ("From research" or "Added by you", plus an "only unverifiable evidence" flag);
- add, edit and dismiss controls.

## Acceptance criteria

- [x] Every competitor or alternative links to at least one evidence item, or is marked "added
      by user".
      - Research entries without stored evidence are rejected (tested).
      - Manual entries show "Added by you" and "No linked evidence".
      - Live: all 8 imported entries have 1–3 linked evidence items.
- [x] Manual and service alternatives appear when the sources mention them. Live: "Spreadsheets
      and free report templates", "Email, text and phone" and "Lender construction monitoring
      firms" (service).
- [x] The summary contains only cited claims; empty input gives "No evidence found."
      - Claims citing rejected refs are dropped (tested).
      - The UI shows "No evidence found." for an empty summary and for empty kinds.
      - Live: a 5-claim summary, every claim cited.
- [x] The user can add, edit and dismiss entries. Browser check:
      - add (duplicate names get a 409 with a clear message);
      - edit a research entry (badge becomes "From research · edited by you");
      - dismiss; zero unexpected console errors.
      - Re-imports keep user edits and dismissals (tested).

**Live run:** method v2 step 5b on "Construction progress automation". 16 of 16 quotes verified
(6 deduplicated re-citations), 8 competitors across all four kinds. Report:
`research/construction-progress-reports/report-2026-11-02.md`.

## Notes carried forward

- **Customer sentiment is thin.** Independent review sites (G2, Capterra, TrustRadius) block
  Preuve's crawler. The only verifiable Procore complaint came from a competitor's blog and is
  flagged as biased. Interviews (Phase 3) are where real sentiment will come from.
- **Pricing is often missing or stale.** Vendors hide pricing behind demos, and Raken's own site
  blocks the crawler, so its pricing comes from an undated article. `pricing_note` should always
  say how fresh it is.
- Pack schema is now **1.1**; 1.0 packs still import. The skill is at **method v2**.

## Decisions (2026-11-02)

- Founder-listed competitors are verified via the skill (see the kickoff plan), not by separate
  auto-fetching.
- The synthesis is written by the researcher and verified by Preuve; there's no Gemini call in
  this phase.
