"""Benchmark local Ollama models on Preuve-shaped tasks with known answers.

Run: uv run python -m app.scripts.llm_bench llama3.1:8b qwen2.5:7b
Scores accuracy, schema validity, grounding (no invented facts / evidence ids) and latency.
"""

import asyncio
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel

from app.core.config import get_settings
from app.llm.base import LLMError
from app.llm.guardrails import EVIDENCE_RULES, Claim
from app.llm.ollama import OllamaProvider

# ---------- schemas (shapes the real phases will use) ----------


class ReplyClassification(BaseModel):
    sentiment: Literal["positive", "neutral", "negative"]
    problem_confirmed: Literal["yes", "no", "unclear"]
    recommended_action: Literal["interview", "follow_up", "close"]


class JobPostingFields(BaseModel):
    role_title: str
    mentions_manual_reporting: bool
    report_frequency: Literal["daily", "weekly", "monthly", "none_stated"]
    tools_mentioned: list[str]


class EvidenceRelevance(BaseModel):
    relevance: Literal["high", "medium", "low"]
    supports_hypothesis: bool


class GroundedAnswer(BaseModel):
    answer: str | None  # null when the source doesn't say
    quote: str | None  # verbatim supporting quote, or null


class ClaimSet(BaseModel):
    claims: list[Claim]


REPLY_SYSTEM = """You classify replies to customer-research emails.
sentiment: the person's attitude toward talking about the problem.
  positive = open/interested (even if they describe pain), neutral = non-committal,
  negative = refuses.
problem_confirmed: "yes" only if they say they experience the problem; "no" if they say they don't;
  otherwise "unclear".
recommended_action: interview = willing to talk; follow_up = needs more info or later;
  close = declined."""

# ---------- cases ----------


@dataclass
class Case:
    name: str
    schema: type[BaseModel]
    prompt: str
    check: Callable[[Any], bool]
    system: str | None = None


CASES: list[Case] = [
    Case(
        "reply: pain + interest",
        ReplyClassification,
        "Reply: 'We have this problem every week. Our PMs lose 4-5 hours on reports. "
        "Happy to chat.'",
        lambda r: (
            (r.sentiment, r.problem_confirmed, r.recommended_action)
            == ("positive", "yes", "interview")
        ),
        REPLY_SYSTEM,
    ),
    Case(
        "reply: polite decline",
        ReplyClassification,
        "Reply: 'Thanks, but reporting isn't really an issue for us. Please remove me.'",
        lambda r: (
            (r.sentiment, r.problem_confirmed, r.recommended_action) == ("negative", "no", "close")
        ),
        REPLY_SYSTEM,
    ),
    Case(
        "reply: later",
        ReplyClassification,
        "Reply: 'Busy with a project close-out. Can you send a short summary and ping me "
        "next month?'",
        lambda r: r.problem_confirmed == "unclear" and r.recommended_action == "follow_up",
        REPLY_SYSTEM,
    ),
    Case(
        "reply: complaint but no time",
        ReplyClassification,
        "Reply: 'Honestly our weekly reports are a nightmare, but I have zero time for calls.'",
        lambda r: r.problem_confirmed == "yes" and r.recommended_action != "interview",
        REPLY_SYSTEM,
    ),
    Case(
        "extract: job posting",
        JobPostingFields,
        "Job posting: 'Project Coordinator — ABC Builders, Dallas TX. Prepare weekly progress "
        "reports for owners using Procore and Excel; collect site photos from superintendents; "
        "maintain RFI logs.'",
        lambda r: (
            r.mentions_manual_reporting
            and r.report_frequency == "weekly"
            and {"procore", "excel"} <= {t.lower() for t in r.tools_mentioned}
        ),
    ),
    Case(
        "extract: no reporting",
        JobPostingFields,
        "Job posting: 'Carpenter — framing crew, Phoenix AZ. 3+ years experience, own tools, "
        "valid driver license.'",
        lambda r: not r.mentions_manual_reporting and r.report_frequency == "none_stated",
    ),
    Case(
        "relevance: irrelevant snippet",
        EvidenceRelevance,
        "Hypothesis: construction PMs spend significant time on manual progress reports.\n"
        "Snippet: 'Our company picnic raised $5,000 for the local food bank this summer.'",
        lambda r: r.relevance == "low" and not r.supports_hypothesis,
    ),
    Case(
        "relevance: strong snippet",
        EvidenceRelevance,
        "Hypothesis: construction PMs spend significant time on manual progress reports.\n"
        "Snippet: 'Every Friday I spend half my day stitching photos and notes into the owner "
        "report by hand.' — project manager on a construction forum",
        lambda r: r.relevance == "high" and r.supports_hypothesis,
    ),
    Case(
        "grounding: answer absent",
        GroundedAnswer,
        "Source: 'ABC Builders is a general contractor in Dallas founded in 1998 that focuses on "
        "healthcare facilities.'\nQuestion: How many employees does ABC Builders have? "
        "If the source does not say, answer null.",
        lambda r: r.answer is None or r.answer.strip().lower() in {"", "null", "unknown"},
        EVIDENCE_RULES,
    ),
    Case(
        "grounding: answer present",
        GroundedAnswer,
        "Source: 'ABC Builders is a general contractor in Dallas founded in 1998 that focuses on "
        "healthcare facilities.'\nQuestion: When was ABC Builders founded?",
        lambda r: r.answer is not None and "1998" in r.answer and r.quote and "1998" in r.quote,
        EVIDENCE_RULES,
    ),
    Case(
        "claims: only real evidence ids",
        ClaimSet,
        "Evidence:\n[ev-101] Job posting at ABC Builders: 'prepare weekly progress reports'.\n"
        "[ev-102] Forum post by a PM: 'reports eat my Fridays'.\n"
        "Task: list claims about whether construction PMs find reporting burdensome.",
        lambda r: (
            bool(r.claims)
            and all(set(c.evidence_ids) <= {"ev-101", "ev-102"} for c in r.claims)
            and any(c.kind == "fact" for c in r.claims)
        ),
        EVIDENCE_RULES,
    ),
]

# ---------- runner ----------


@dataclass
class Score:
    model: str
    passed: int = 0
    invalid: int = 0
    latencies: list[float] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


async def bench(model: str, rounds: int) -> Score:
    s = get_settings()
    provider = OllamaProvider(s.ollama_url, model, num_ctx=8192, timeout_s=300)
    score = Score(model)
    await provider.generate_text("Say ok.")  # warm-up: load the model into memory
    for _ in range(rounds):
        for case in CASES:
            started = time.perf_counter()
            try:
                result = await provider.generate_structured(
                    case.prompt, case.schema, system=case.system
                )
                ok = bool(case.check(result))
            except LLMError as exc:
                score.invalid += 1
                ok = False
                result = f"invalid: {str(exc)[:80]}"
            score.latencies.append(time.perf_counter() - started)
            if ok:
                score.passed += 1
            else:
                score.failures.append(f"{case.name}: {result}")
    return score


async def main(models: list[str], rounds: int = 2) -> None:
    total = len(CASES) * rounds
    for model in models:
        sc = await bench(model, rounds)
        avg = sum(sc.latencies) / len(sc.latencies)
        print(
            f"\n== {model}: {sc.passed}/{total} passed, {sc.invalid} invalid, "
            f"avg {avg:.1f}s, max {max(sc.latencies):.1f}s"
        )
        for f in sc.failures:
            print(f"   x {f}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or [get_settings().ollama_model]))
