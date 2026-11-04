# Phase 4 — Validation & decision

- **Status:** In progress (kickoff 2026-11-04)
- **Goal:** Combine all stored evidence into a reproducible score, a validation state and an
  explained recommendation, including telling the founder "don't build yet".
- **PRD refs:** §24 Validation scoring, §25 Validation states, §26 Decision engine,
  §27 Portfolio, §28 Experiments, §44 Validation report, §47–§48 metrics, §51 philosophy

## Principles

- **Code decides, the model only words it.** Score, state, recommendation, strong/weak evidence,
  biggest uncertainty, next actions and metrics are computed by pure functions over stored rows.
  No LLM touches a number or a verdict.
- **Only counted evidence counts.** Dismissed evidence never counts. Research evidence counts only
  when `verified` (unverifiable items are listed as a weak spot). First-party signals count only
  through their stored `evidence` rows (i.e. quotes that verified in Phase 3).
- **Independence.** A *customer* is a contact, else a company, else the reply sender's address /
  interviewee name (normalised). Research sources are independent per domain. Five quotes from
  one customer are one customer.
- **Absence is not rejection.** Missing evidence leads to INVESTIGATE FURTHER ("don't build
  yet"), never to ABANDON. ABANDON needs customers actively contradicting the problem.

## Validation score (PRD §24) — `SCORING_VERSION = 2`

Pure function `score(ValidationInput) -> ScoreResult`, like lead scoring (1D). Each dimension
stores `points`, `max`, `reason`, `evidence_ids` and `gaps` (what would raise it). Points are
clamped to `[0, max]`; the total is their sum. All constants live in one block in `scoring.py`.

| Dimension | Max | Rule |
|---|---|---|
| Problem evidence | 20 | +3 per customer confirming the problem (reply `problem confirmed: yes`, or interview `problem` evidence), max 12; +2 per independent domain of verified, supporting, medium/high-relevance research evidence, max 8; −3 per customer denying it (`problem confirmed: no`); −2 per domain of verified contradicting research, max 8 (same cap as support, so sources never outweigh customers either way). |
| Problem frequency | 10 | +2 per customer with a frequency quote (reply or interview), max 8; +1 per verified supporting research item linked to a `frequency` unknown, max 2. |
| Problem severity | 15 | Per customer: severity high +3, medium +1, low −2; a quantified time/cost quote +2. Max 13 from customers; +1 per verified supporting research item linked to a `cost`/`urgency` unknown, max 2. |
| Customer response | 15 | +2 per customer with a positive reply or high/medium interest, max 10; reply rate ≥ 10 % on ≥ 10 sent +5 (≥ 5 % on ≥ 10 sent +2). |
| Interview confirmation | 15 | +5 per *done* interview with supporting problem/frequency/cost evidence, max 15. Interviews with only objections add nothing and are listed as weak evidence. |
| Existing alternatives | 10 | +2 per customer naming their current solution / workflow / alternatives, max 6; +1 per active competitor or alternative with linked evidence, max 4; −2 per customer highly satisfied with their current solution. |
| Willingness to pay | 15 | Per customer, the best of: paid 15, signed 12, pilot 8, verbal 4, stated strong 3, stated some 2; stated none −2. Summed, max 15. Commitments are user-set only (Phase 3). |

`inputs_hash` = SHA-256 of the canonical JSON of the inputs + `SCORING_VERSION`. Same inputs →
same score (tested).

## Validation states (PRD §25)

Rule-based; the highest state whose conditions hold is written to `ideas.state` on every score
recompute. Thresholds (agreed at kickoff, one constants block):

| State | Condition |
|---|---|
| UNVALIDATED | Nothing below holds. |
| RESEARCHING | An analysis run or research import exists. |
| EARLY SIGNAL | ≥ 1 customer confirms the problem, or ≥ 3 independent domains of verified supporting research. |
| PROBLEM VALIDATED | ≥ 3 independent **companies** confirm the problem, ≥ 1 of them in a done interview, and confirmations ≥ 2 × denials. |
| SOLUTION VALIDATION | Problem validated + ≥ 3 customers with high interest. |
| COMMERCIAL VALIDATION | Problem validated + ≥ 2 pilot-or-better commitments, or ≥ 1 paid. |
| MVP READY | Commercial validation + score ≥ 70 + ≥ 5 done interviews. |

## Decision engine (PRD §26)

| Recommendation | When |
|---|---|
| BUILD | State is MVP READY. |
| ABANDON | ≥ 3 customers deny the problem and denials ≥ confirmations. |
| ITERATE | Some confirmation but a specific contradiction: denials > 0 and confirmations < 2 × denials; or problem validated but ≥ 2 customers state no WTP and nobody committed; or ≥ 2 customers highly satisfied with their current solution. |
| INVESTIGATE FURTHER | Everything else — headline: **"Weak evidence. Don't build yet."** when score < 40. |

Every decision carries:
- **strong evidence:** facts like "4 customers confirmed the problem", each with evidence ids;
- **weak evidence:** dimensions under 50 % of their max, contradictions, unverifiable items,
  objections, stated-but-uncommitted WTP;
- **biggest uncertainty:** the dimension with the most missing points (ties: PRD weight order),
  or the highest-priority open unknown if research is still open;
- **next actions:** deterministic templates from the gaps (e.g. "Interview 2 more customers to
  reach 3 independent confirmations"), plus open unknowns, high priority first.

## Metrics (PRD §47–§48)

Shown with the score, deterministic:
- **Validated customer conversations** (north star): customers with ≥ 1 counted first-party
  evidence item from a reply or a done interview.
- Response rate (replied messages / sent), problem confirmation rate (customers confirming /
  validated conversations), interview conversion (done interviews / positive replies),
  commercial validation (pilot-or-better customers / validated conversations).

## Experiments (PRD §28)

- An experiment: hypothesis, cohort A and optional cohort B, status (`running` / `concluded`),
  conclusion (user text), result snapshot (json, frozen on conclude).
- A cohort is a filter over sent outreach: campaigns and/or ICP and/or a contact-role keyword
  (e.g. "operations director" vs "project manager").
- Results are computed live from sent messages and their replies: sent, replies, reply rate,
  positive, problem confirmed, interview recommended, interviews done. A comparison line is
  stated only as counts ("Cohort A: 4/10 positive; cohort B: 2/10"), with a "sample too small"
  flag under 10 sent per cohort. The conclusion is written by the user, not the model.

## Validation report (PRD §44)

- Generated by `validation_report_job` from a stored score snapshot. The Markdown body is
  **rendered by code**: idea, verdict, score and dimension table, state, problem / solution /
  WTP status, evidence count, conversations, interviews, strongest signal, biggest uncertainty,
  strong/weak evidence with exhibit refs, next actions, metrics, and an evidence appendix
  (quote, source URL or `preuve://` ref, fetched-at).
- The only LLM part is a short **summary** (`validation_report`), returned as `Claim`s; facts must
  cite evidence ids that are in the snapshot (`verify_citations`), and a summary sentence that
  contains a digit not present in the score record is dropped. The call uses `private=True`
  because first-party quotes are included: local model by default, Gemini only with
  `ALLOW_PRIVATE_TO_GEMINI=true`. If the call fails or returns nothing, the report says
  "No summary — the model returned no cited claims." and is still complete.
- Export: `GET /reports/{id}/markdown` (Markdown download) and a print-optimised report page
  (browser "Save as PDF"). No server-side PDF dependency.

## Portfolio (PRD §27)

The existing `GET /portfolio` gains: latest score, recommendation, validated conversations,
replies, done interviews and pilot-or-better commitments. The case board shows them and can be
sorted by score.

## Out of scope

Automated experiment generation, landing pages, pre-orders, pricing experiments (PRD §49).
Auto-recomputing the score on every evidence change (it's recomputed on demand; the UI shows
when stored inputs changed since the last score).

## Data model

| Table | Key columns |
|---|---|
| `validation_scores` | idea_id, total, dimensions (json), state, recommendation, decision (json: headline, strong, weak, uncertainty, next_actions), metrics (json), inputs (json, the canonical inputs), inputs_hash, scoring_version, created_at |
| `experiments` | idea_id, hypothesis, cohort_a (json), cohort_b (json?), status, result (json?), conclusion, concluded_at |
| `reports` | idea_id, validation_score_id, status (`queued`/`running`/`done`/`failed`), content (md), summary (json claims), dropped (json), error, created_at |

## API

- `GET /ideas/{id}/score` (latest snapshot + `stale` when current inputs hash differs),
  `POST /ideas/{id}/score` (recompute, store a snapshot, update `ideas.state`),
  `GET /ideas/{id}/score/history`.
- `GET/POST /ideas/{id}/experiments`, `GET/PATCH/DELETE /ideas/{id}/experiments/{eid}`
  (results computed on read; PATCH can conclude).
- `POST /ideas/{id}/reports` (enqueue), `GET /ideas/{id}/reports`, `GET /reports/{id}`,
  `GET /reports/{id}/markdown`, `DELETE /reports/{id}`.
- `GET /portfolio` (extended).

## Jobs

`validation_report_job(report_id)`.

## LLM tasks

| Task | Provider | Notes |
|---|---|---|
| `validation_report` | Gemini chain, but `private=True` ⇒ local unless opted in | Short summary only, as cited `Claim`s; `verify_citations` enforced; numbers come from the DB. |

## UI (Dossier design)

- **Verdict** tab on the dossier: score card with the seven-dimension breakdown (points / max,
  reason, exhibit links, gaps), state badge, recommendation panel (headline, strong, weak,
  biggest uncertainty, next actions), metrics strip, "Recompute" with a stale notice.
- **Experiments** in the same tab: list, create form (cohorts), live result comparison, conclude.
- **Report** view: generated reports, Markdown download, print-optimised layout.
- **Case board:** score, recommendation and funnel counts per idea; sort by score.

## Acceptance criteria

- [ ] The score is fully reproducible from DB data (same inputs, same output; tested).
- [ ] Every recommendation lists the evidence behind it, plus its weak spots.
- [ ] A fixture idea with weak evidence is told not to build yet (tested).
- [ ] The report contains only cited claims; numbers match the score record.
- [ ] Validation state transitions follow the thresholds above (tested per state).
- [ ] Experiments compare cohorts from real outreach/reply data (tested).
- [ ] Private text never reaches Gemini for the report unless opted in (tested).
- [ ] Web lint, typecheck and build pass; verdict, experiments, report and board checked in a
      real browser.

## Decisions (2026-11-04)

- Report = deterministic Markdown + an LLM-written cited summary, `private=True`.
- State thresholds as in the table above.
- PDF via print stylesheet; Markdown via download.
- Score recomputed on demand and stored as snapshots; `ideas.state` follows the latest one.

## Notes

- From Phase 3: first-party evidence reuses `evidence` (`origin` reply/interview) and
  is already linked to responses/interviews/companies; WTP keeps stated and committed apart, and
  only commitments count heavily here.
- Local-model extraction is sparse (2–3 of 10 interview fields), so interview-based dimensions
  will often be low; that's honest, and the gaps say what to ask next.
- Restart the arq worker after pulling (a stale worker swallows unknown job types).
