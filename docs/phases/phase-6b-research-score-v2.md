# Phase 6B — Research score v2 (stop saturation, price in crowding)

- **Status:** In progress (kickoff 2026-11-06)
- **Goal:** Make the research score separate ideas after thorough research. Version 1 maxed out
  problem, pain and alternatives for every well-researched idea, so ideas were ranked mostly on
  prospect counts. It also ignored the most common finding: the wedge is already taken.
- **PRD refs:** §24, §27; builds on [Phase 6](phase-6-research-score.md)

## What v1 got wrong (observed on 8 researched cases, 2026-11-05/06)

- **Problem (30), pain (15) and alternatives (5) saturate.** Every thorough research run finds 10 or
  more supporting domains, so all of them scored 30/15/5 and the totals bunched at 83–87.
- **Vendor marketing pages counted the same as people describing their own pain.**
- **Crowding wasn't priced.** "Free tools and direct competitors already do this" was the main
  contradicting finding in most cases, and v1 *rewarded* it (more mapped alternatives = more points).

## Research score — `RESEARCH_SCORE_VERSION = 2`

Counted research is unchanged: research-origin evidence that is verified, not dismissed, with
relevance medium or high. Sources are still counted once per domain per dimension. A domain's
weight is the best source type it has for that dimension:

| Source type | Weight | Why |
|---|---|---|
| `forum`, `review`, `job_posting` | 3 | Buyers or employers describing the pain first-hand |
| `news`, `industry_publication`, `report` | 2 | Independent reporting |
| `company_site`, `directory`, `other` | 1 | Vendors describe the problem they sell against |

Diminishing returns replace hard caps, so more and better evidence always helps a little and
nothing saturates: `points = round(max × W / (W + half))`, where `W` is the summed weight and `half`
is the weight that earns half the points.

| Dimension | Max | Rule |
|---|---|---|
| Problem evidence | 25 | Weighted supporting domains, `half = 15` (≈ 5 first-hand forums for 12–13 points). |
| Pain depth | 15 | Weighted supporting domains linked to a `cost`, `urgency` or `frequency` unknown, `half = 9`. |
| Evidence balance | 20 | With S supporting and C contradicting domains (unweighted): 0 if S = 0, else `round(20 × S/(S+C) × min(1, (S+C)/8))`. |
| Questions answered | 10 | As v1 (priority-weighted finding credit), scaled to 10. |
| Open space | 15 | `15 − 3 × direct − 1 × indirect`, floored at 0. Counts active competitors that have at least one verified evidence item; `manual` and `service` alternatives don't count as crowding. |
| Reachability | 15 | As v1: +1 per prospect company (max 10), +1 per named contact (max 5). |

The bands stay the same: strong ≥ 60, promising 40–59, weak < 40.

## Scope

- `research_score.py`: v2 rules. It gets its own input dataclasses (`ResearchSource` with
  `source_type`, `CompetitorEntry` with `kind`) so the validation score's canonical inputs and hashes
  don't change.
- `validation.service.research_score_input` passes the source type and competitor kind.
- Doc, tests and UI copy ("Alternatives mapped" becomes "Open space").

## Out of scope

Parsing competitor prices; LLM judgments; snapshots.

## Data model / API / jobs / LLM

No changes. The endpoint and portfolio field keep their shape, and `version` becomes 2.

## Acceptance criteria

- [ ] Problem and pain never reach their max with finite evidence, and weighting by source type works (tests).
- [ ] Open space falls with direct and indirect competitors, and manual or service alternatives don't count (tests).
- [ ] Validation-score inputs and hashes are unchanged (the existing validation tests pass).
- [ ] Live: the 8 researched cases spread more widely than v1's 73–87, and crowded wedges rank lower.
- [ ] `ruff check`, `ruff format --check`, `pytest`, web lint and typecheck pass.

## Open questions (settled at kickoff)

- *Use competitor prices for "free or cheap"?* No. `pricing_note` is free text and seldom present;
  the competitor kind assigned during research is the deterministic signal.
- *Keep "alternatives mapped"?* No. Mapping alternatives is research hygiene, not idea quality,
  and it double-counted against open space.
