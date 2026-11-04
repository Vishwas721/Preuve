# Preuve — Roadmap

Preuve is built in small phases. Each phase has its own doc in [`phases/`](phases/), covering
scope, data model, API, jobs, LLM tasks, UI, acceptance criteria and open questions. How a
phase runs is described in [`phases/README.md`](phases/README.md).

Nothing from a later phase is built early. Every phase ends with a review stop.

| Phase | Doc | Status |
|---|---|---|
| 0 — Foundation | [phase-0-foundation.md](phases/phase-0-foundation.md) | ✅ Done |
| 1A — Idea intake & analyzer | [phase-1a-idea-analyzer.md](phases/phase-1a-idea-analyzer.md) | ✅ Done |
| 1B — Research import & verification | [phase-1b-research-evidence.md](phases/phase-1b-research-evidence.md) | ✅ Done |
| 1C — Competitors & alternatives | [phase-1c-competitors.md](phases/phase-1c-competitors.md) | ✅ Done |
| 1D — Prospects, enrichment & scoring | [phase-1d-prospects-scoring.md](phases/phase-1d-prospects-scoring.md) | ✅ Done |
| 1E — Phase 1 UI | [phase-1e-phase1-ui.md](phases/phase-1e-phase1-ui.md) | ✅ Done |
| 2 — Outreach | [phase-2-outreach.md](phases/phase-2-outreach.md) | ✅ Done |
| 3 — Responses & interviews | [phase-3-responses-interviews.md](phases/phase-3-responses-interviews.md) | ✅ Done |
| 4 — Validation & decision | [phase-4-validation-decision.md](phases/phase-4-validation-decision.md) | 🟡 In progress |
| 5 — Hardening | [phase-5-hardening.md](phases/phase-5-hardening.md) | ⬜ |

Phases 1A–1E together form the PRD's "MVP Phase 1" (§45). Phases 2, 3 and 4 correspond to the
PRD's MVP Phases 2, 3 and 4.

## Flow

```
1A idea → hypothesis, unknowns, ICPs
 ↓
1B Claude Code researches (/research-idea) → Preuve verifies quotes → evidence
 ↓
1C competitors / alternatives          1D companies → contacts → lead scores
 ↓                                      ↓
1E UI: dashboard, idea detail, research explorer, prospect explorer
 ↓
2  outreach drafts → human approval → send (with safety limits)
 ↓
3  replies + interviews → first-party evidence, willingness to pay
 ↓
4  validation score → state → decision → report
 ↓
5  auth, teams, privacy, deployment
```
