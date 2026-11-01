# Phase docs

One document per roadmap phase. The overview and status table live in [`../ROADMAP.md`](../ROADMAP.md).

## How a phase runs

1. **Kickoff.** Re-read the phase doc and the PRD sections it cites. Refine the doc: settle the
   open questions and turn its draft scope into a concrete plan. Commit the refined doc first.
2. **Build.** Small single-purpose commits, each pushed to `main`. Nothing from a later phase.
3. **Verify.** Tick every acceptance criterion with real evidence: tests, a live run, screenshots.
4. **Close.** Set the status to `Done` here and in `ROADMAP.md`, record any notes carried
   forward, then stop for review.

## Template

Each phase doc has the same sections:

- **Status / Goal / PRD refs**
- **Scope** (in) and **Out of scope**
- **Data model**: new tables only; earlier tables are reused, never duplicated
- **API**: new endpoints
- **Jobs**: arq background work
- **LLM tasks**: `TaskType`s used and their default provider
- **UI**
- **Acceptance criteria**
- **Open questions**: settled at kickoff
- **Notes**: carried forward from earlier phases or discovered during the build

Docs for phases that haven't started are **drafts**. Their details will change at kickoff.
