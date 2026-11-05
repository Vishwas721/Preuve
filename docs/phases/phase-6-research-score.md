# Phase 6 — Research score (rank ideas before outreach)

- **Status:** In progress (kickoff 2026-11-05)
- **Goal:** Rank ideas on public-web evidence alone, before any customer contact, so the founder can
  work down the list and start outreach with the most promising idea first.
- **PRD refs:** §24 Validation scoring (the score this precedes), §27 Portfolio, §51 philosophy

## Why a second score

The validation score (Phase 4) is mostly about customers: replies, interviews and willingness to
pay. Public research can add at most about 16 of its 100 points, so every un-contacted idea sits
near the bottom and they can't be told apart. The research score answers a different question:
*"Given what the web shows, which idea is most worth contacting customers about first?"*

It never replaces the validation score, and it never changes an idea's state or recommendation.
A high research score means "worth testing with customers", not "validated".

## Principles

- **Code decides.** A pure function over stored rows, like the lead and validation scores. No LLM.
- **Only verified research counts.** Dismissed or unverifiable evidence and first-party
  evidence don't count.
- **Independence.** Sources count once per domain per dimension. Ten quotes from one site make
  one source.
- **Contradictions cost.** Contradicting sources lower the score through the balance dimension.
- **Live, not snapshotted.** It is cheap and fully determined by stored rows, so it is computed
  on read. There is no table, no "stale" flag and no recompute button. `RESEARCH_SCORE_VERSION`
  marks rule changes.

## Research score — `RESEARCH_SCORE_VERSION = 1`

Counted research = research-origin evidence that is verified, not dismissed, with relevance
medium or high. "Domains" means independent domains (`domain_key` of the final URL).

| Dimension | Max | Rule |
|---|---|---|
| Problem evidence | 30 | +3 per domain with counted **supporting** evidence, max 30 (10 domains). |
| Pain depth | 15 | +3 per domain with counted supporting evidence linked to a `cost`, `urgency` or `frequency` unknown, max 15. |
| Evidence balance | 20 | With S supporting and C contradicting domains: 0 if S = 0, else `round(20 × S/(S+C) × min(1, (S+C)/5))`. One-sided evidence scores full only once there are 5 or more sources. |
| Questions answered | 15 | Each unknown is weighted by priority (high 3, medium 2, low 1). Its latest research finding counts as answered 1, partially answered 0.5, and no evidence or no finding 0. `round(15 × achieved / possible)`; 0 when there are no unknowns. |
| Alternatives mapped | 5 | +1 per competitor or alternative with at least one counted (verified) evidence item, max 5. |
| Reachability | 15 | +1 per prospect company, max 10; +1 per named contact, max 5. |

Each dimension returns `points`, `max`, `reason` and `gaps` (what would raise it), the same shape
as the validation dimensions. Bands, for display only: **strong** ≥ 60, **promising** 40–59,
**weak** < 40.

## Scope

- `app/modules/validation/research_score.py`: inputs, constants and the pure `research_score()`.
- `validation.service.research_score_for(session, idea)` builds the inputs through other
  modules' service functions.
- API: `GET /ideas/{idea_id}/research-score`.
- Portfolio: each item gains `research_score {total, band, version}`, and `GET /portfolio` items can be
  ranked by it.
- UI: the case board shows the research score on each folder and gains a **Research** sort (now
  the default, since ranking for outreach is the point). The case overview gets a
  "Research score" section with the dimension bars and gaps.

## Out of scope

Storing snapshots or history; changing states, recommendations or the validation score;
LLM-written explanations; weighting by source type (job postings vs blogs).

## Data model

None. Computed from existing tables.

## Jobs / LLM tasks

None.

## Acceptance criteria

- [ ] Pure function: the same inputs give the same result, and each dimension is clamped to [0, max] (unit tests).
- [ ] Unverifiable, dismissed, low-relevance and first-party evidence don't count (tests).
- [ ] Domains are counted once per dimension (test).
- [ ] Contradicting domains lower the balance dimension, and one-sided thin evidence doesn't score full balance (tests).
- [ ] `GET /ideas/{id}/research-score` returns the dimensions; `GET /portfolio` includes `research_score` (API tests).
- [ ] The case board shows the research score and sorts by it; the overview shows the breakdown.
- [ ] Live check on the two researched cases: they rank in a sensible order, and the totals match a hand calculation.
- [ ] `ruff check`, `ruff format --check`, `pytest`, web lint and typecheck pass.

## Open questions (settled at kickoff)

- *Snapshot or live?* Live, because there are no expensive inputs and live avoids staleness.
- *Should reachability count?* Yes, but only up to 15 points, because the founder's next step is
  emailing prospects. A strong problem with no reachable prospects should still rank above a
  weak problem with many prospects; the weights guarantee that (problem + balance = 50 points).

## Notes

- Constants live in one block in `research_score.py`; changing one means bumping
  `RESEARCH_SCORE_VERSION` and updating this doc.
