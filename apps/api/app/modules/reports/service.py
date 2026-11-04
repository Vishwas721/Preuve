"""Validation reports (PRD §44).

The report body is rendered by code from one stored score snapshot, so every number in it is the
snapshot's. The only model-written part is a short summary of `Claim`s; each must cite exhibits of
this report and use only numbers already in the snapshot or the cited quotes. The call is
`private=True` because reply and interview quotes are included.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import LLMError
from app.llm.router import LLMRouter
from app.llm.tasks import TaskType
from app.modules.ideas.models import Idea
from app.modules.reports import prompts
from app.modules.reports.models import Report, ReportStatus
from app.modules.research import service as research
from app.modules.validation import service as validation
from app.modules.validation.models import ValidationScore

logger = logging.getLogger(__name__)

NO_SUMMARY = "No summary: the model returned no cited claims."

RECOMMENDATION_LABELS = {
    "build": "BUILD",
    "iterate": "ITERATE",
    "investigate": "INVESTIGATE FURTHER",
    "abandon": "ABANDON",
}
STATE_LABELS = {
    "unvalidated": "Unvalidated",
    "researching": "Researching",
    "early_signal": "Early signal",
    "problem_validated": "Problem validated",
    "solution_validation": "Solution validation",
    "commercial_validation": "Commercial validation",
    "mvp_ready": "MVP ready",
}


class ReportError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _pct(v: float | None) -> str:
    return "n/a" if v is None else f"{round(v * 100)}%"


# ---------- exhibits ----------


def exhibit_order(score: ValidationScore) -> list[str]:
    """Evidence ids in the order the report first cites them: dimensions, then strong/weak."""
    ids: list[str] = []
    for d in score.dimensions:
        ids += d["evidence_ids"]
    for key in ("strong", "weak"):
        for p in score.decision[key]:
            ids += p["evidence_ids"]
    return list(dict.fromkeys(ids))


def _refs(ids: list[str], refs: dict[str, str]) -> str:
    cited = [refs[i] for i in ids if i in refs]
    return f" [{', '.join(cited)}]" if cited else ""


# ---------- rendering ----------


def _md(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render(
    idea: Idea,
    score: ValidationScore,
    evidence: dict[str, dict[str, Any]],
    refs: dict[str, str],
    summary: list[dict],
    generated_at: datetime,
) -> str:
    f, m, dec = score.facts, score.metrics, score.decision
    rec = RECOMMENDATION_LABELS.get(score.recommendation, score.recommendation)
    out: list[str] = []
    add = out.append

    add(f"# Validation report: {idea.title}")
    add("")
    add(
        f"_Generated {generated_at:%Y-%m-%d %H:%M} UTC from the score computed "
        f"{score.created_at:%Y-%m-%d %H:%M} UTC (scoring v{score.scoring_version}). "
        "Numbers, verdict and evidence lists are computed by fixed rules; only the summary is "
        "written by a model._"
    )
    add("")
    add("## Verdict")
    add("")
    add(f"**{dec['headline']}**")
    add("")
    add(f"- Recommendation: **{rec}**")
    add(f"- Score: **{score.total}/100**")
    add(f"- Validation state: **{STATE_LABELS.get(score.state.value, score.state.value)}**")
    add(f"- Why: {dec['why']}")
    add("")

    add("## Summary")
    add("")
    if summary:
        for c in summary:
            add(f"- {c['statement']}{_refs(c['evidence_uuids'], refs)}")
        add("")
        add("_Model-written. Each sentence cites the exhibits it rests on._")
    else:
        add(NO_SUMMARY)
    add("")

    problem = (
        "Validated"
        if score.state.value
        in ("problem_validated", "solution_validation", "commercial_validation", "mvp_ready")
        else "Not yet validated"
    )
    add("## Status")
    add("")
    add("| | Status | Basis |")
    add("|---|---|---|")
    add(
        f"| Problem | {problem} | {f['confirming_customers']} customers confirmed "
        f"({f['confirming_companies']} companies, {f['confirming_in_interview']} in interviews), "
        f"{f['denying_customers']} denied |"
    )
    add(
        f"| Solution interest | {f['high_interest_customers']} customers with high interest | "
        "from replies |"
    )
    add(
        f"| Willingness to pay | {f['pilot_or_better']} pilot-or-better commitments "
        f"({f['paid']} paid) | {f['no_wtp_customers']} said they wouldn't pay |"
    )
    n_research = sum(1 for e in evidence.values() if e["origin"].value == "research")
    add(
        f"| Evidence | {len(evidence)} exhibits cited | {n_research} research, "
        f"{len(evidence) - n_research} first-party |"
    )
    add(
        f"| Conversations | {f['validated_conversations']} validated customer conversations | "
        f"{f['replies']} replies to {f['sent']} sent |"
    )
    add(f"| Interviews | {f['interviews_done']} done | |")
    add("")

    strongest = max(
        (d for d in score.dimensions if d["points"] > 0),
        key=lambda d: d["points"] / d["max"],
        default=None,
    )
    add("## Strongest signal")
    add("")
    add(
        f"{strongest['label']} {strongest['points']}/{strongest['max']}: {strongest['reason']}"
        f"{_refs(strongest['evidence_ids'], refs)}"
        if strongest
        else "No evidence found."
    )
    add("")
    add("## Biggest uncertainty")
    add("")
    add(dec["uncertainty"])
    add("")

    add("## Score breakdown")
    add("")
    add("| Dimension | Points | Reason | Exhibits |")
    add("|---|---|---|---|")
    for d in score.dimensions:
        cited = _refs(d["evidence_ids"], refs).strip(" []") or "none"
        add(f"| {d['label']} | {d['points']}/{d['max']} | {_md(d['reason'])} | {cited} |")
    add(f"| **Total** | **{score.total}/100** | | |")
    add("")

    for key, title in (("strong", "Strong evidence"), ("weak", "Weak evidence")):
        add(f"## {title}")
        add("")
        points = dec[key]
        if not points:
            add("No evidence found.")
        for p in points:
            add(f"- {p['text']}{_refs(p['evidence_ids'], refs)}")
        add("")

    add("## Next actions")
    add("")
    for a in dec["next_actions"] or ["None: the evidence meets the build thresholds."]:
        add(f"- {a}")
    add("")

    add("## Metrics")
    add("")
    add(f"- Validated customer conversations (north star): {m['validated_conversations']}")
    add(f"- Response rate: {_pct(m['response_rate'])}")
    add(f"- Problem confirmation rate: {_pct(m['problem_confirmation_rate'])}")
    add(f"- Interview conversion: {_pct(m['interview_conversion'])}")
    add(f"- Commercial validation: {_pct(m['commercial_validation'])}")
    add("")

    add("## Exhibits")
    add("")
    if not refs:
        add("No evidence found.")
    for eid, ref in refs.items():
        e = evidence[eid]
        kind = {"reply": "Reply", "interview": "Interview"}.get(e["origin"].value, "Research")
        add(
            f"- **{ref}** ({kind}, {e['stance'].value}) \u201c{_md(e['quote'])}\u201d "
            f"\u2014 {_md(e['statement'])}. Source: {e['final_url'] or e['url']}, "
            f"fetched {e['fetched_at']:%Y-%m-%d}."
        )
    add("")
    return "\n".join(out)


# ---------- lifecycle ----------


async def create(session: AsyncSession, idea: Idea) -> Report:
    """Snapshot the score (recomputing if the data changed) and queue a report for it."""
    score = await validation.latest(session, idea.id)
    if score is None or score.inputs_hash != await validation.current_hash(session, idea):
        score = await validation.recompute(session, idea)
    row = Report(idea_id=idea.id, validation_score_id=score.id)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


def _allowed_numbers(score: ValidationScore, quotes: list[str]) -> set[str]:
    nums = {str(score.total), "100"}
    nums |= {str(v) for v in score.facts.values()}
    for d in score.dimensions:
        nums |= {str(d["points"]), str(d["max"])}
        nums |= prompts.numbers(d["reason"])
    for v in score.metrics.values():
        if isinstance(v, float):
            nums.add(str(round(v * 100)))
        elif v is not None:
            nums.add(str(v))
    for q in quotes:
        nums |= prompts.numbers(q)
    return nums


async def generate(
    session: AsyncSession, llm: LLMRouter, report_id: uuid.UUID
) -> ReportStatus | None:
    row = await session.get(Report, report_id)
    if row is None:
        return None
    row.status, row.error = ReportStatus.RUNNING, None
    await session.commit()

    idea = await session.get(Idea, row.idea_id)
    score = await session.get(ValidationScore, row.validation_score_id)
    all_ev = {
        str(e["id"]): e
        for e in await research.list_evidence(session, row.idea_id, include_dismissed=True)
    }
    order = [i for i in exhibit_order(score) if i in all_ev]
    refs = {eid: f"E{n}" for n, eid in enumerate(order, 1)}
    by_ref = {v: k for k, v in refs.items()}
    evidence = {eid: all_ev[eid] for eid in order}

    exhibits = [
        prompts.Exhibit(
            ref=refs[eid],
            origin=e["origin"].value,
            stance=e["stance"].value,
            quote=e["quote"],
            statement=e["statement"],
        )
        for eid, e in evidence.items()
    ]
    summary: list[dict] = []
    dropped: list[dict] = []
    if exhibits:
        try:
            out = await llm.structured(
                TaskType.VALIDATION_REPORT,
                prompts.build_prompt(
                    title=idea.title,
                    headline=score.decision["headline"],
                    recommendation=RECOMMENDATION_LABELS[score.recommendation],
                    total=score.total,
                    state=score.state.value,
                    facts=score.facts,
                    dimensions=score.dimensions,
                    exhibits=exhibits,
                ),
                prompts.ReportSummary,
                system=prompts.SYSTEM,
                private=True,  # reply and interview quotes are private
            )
        except LLMError as exc:
            logger.warning("validation_report summary failed for %s: %s", report_id, exc)
            dropped.append({"statement": "", "reason": f"Summary unavailable ({exc})."})
        else:
            for c in out.claims:
                cited = [r for r in c.evidence_ids if r in by_ref]
                quotes = [evidence[by_ref[r]]["quote"] for r in cited]
                why = prompts.check_claim(c, set(by_ref), _allowed_numbers(score, quotes))
                if why:
                    dropped.append({"statement": c.statement, "reason": why})
                    continue
                summary.append(
                    {
                        "statement": c.statement.strip(),
                        "kind": c.kind.value,
                        "evidence_ids": c.evidence_ids,
                        "evidence_uuids": [by_ref[r] for r in c.evidence_ids],
                    }
                )
        chain = llm.chain(TaskType.VALIDATION_REPORT, private=True)
        row.summary_provider = chain[0].value if chain else None

    row.generated_at = _now()
    row.content = render(idea, score, evidence, refs, summary, row.generated_at)
    row.summary, row.dropped, row.exhibits = summary, dropped, refs
    row.status = ReportStatus.DONE
    await session.commit()
    return row.status


async def mark_failed(session: AsyncSession, report_id: uuid.UUID, error: str) -> None:
    row = await session.get(Report, report_id)
    if row is not None and row.status in (ReportStatus.QUEUED, ReportStatus.RUNNING):
        row.status, row.error = ReportStatus.FAILED, error
        await session.commit()


async def list_reports(session: AsyncSession, idea_id: uuid.UUID) -> list[Report]:
    return list(
        await session.scalars(
            select(Report).where(Report.idea_id == idea_id).order_by(Report.created_at.desc())
        )
    )


async def get_report(session: AsyncSession, report_id: uuid.UUID) -> Report | None:
    """No access check: the router authorises through the report's idea."""
    return await session.get(Report, report_id)


async def delete(session: AsyncSession, row: Report) -> None:
    await session.delete(row)
    await session.commit()


async def read(session: AsyncSession, row: Report) -> dict[str, Any]:
    score = await session.get(ValidationScore, row.validation_score_id)
    return {
        **{
            k: getattr(row, k)
            for k in (
                "id",
                "idea_id",
                "validation_score_id",
                "status",
                "content",
                "summary",
                "dropped",
                "exhibits",
                "summary_provider",
                "error",
                "generated_at",
                "created_at",
            )
        },
        "total": score.total if score else None,
        "recommendation": score.recommendation if score else None,
    }
