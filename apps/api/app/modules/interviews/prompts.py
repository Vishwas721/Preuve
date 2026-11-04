"""Prompts, schemas and checks for `interview_guide` and `extract_fields` (PRD §21–§22).

The guide is built only from open unknowns (referenced as U1, U2…), and every question is run
through deterministic leading-question checks. Extraction quotes the notes verbatim.
"""

import re
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.modules.responses.prompts import QuotedText, QuotedWillingness

# ---------- guide ----------

GUIDE_SYSTEM = """\
You prepare a customer-discovery interview guide for a founder. The goal is to LEARN how the
customer works today, not to pitch or to get them to agree. Rules:
1. Write questions ONLY for the open unknowns listed (cite each one's ref, e.g. "U2").
2. Ask about past, concrete behaviour: "Tell me about the last time…", "Walk me through…",
   "How do you handle… today?", "What happened after…?".
3. Never ask yes/no questions. Never ask about the founder's product, never describe a
   solution, never ask "would you use / would you pay for…".
4. Neutral wording: no assumptions that the problem exists ("how painful is…" assumes pain).
5. One main question per unknown, plus up to two short follow-ups.
"""


class GuideQuestion(BaseModel):
    unknown_ref: str = Field(description="The open unknown it addresses, e.g. 'U1'.")
    question: str = Field(min_length=5, max_length=300)
    follow_ups: list[str] = Field(default_factory=list, max_length=2)


class GuideDraft(BaseModel):
    questions: list[GuideQuestion] = Field(default_factory=list, max_length=12)


@dataclass(frozen=True)
class UnknownItem:
    ref: str
    question: str
    category: str


def build_guide_prompt(problem: str, interviewee: str, unknowns: list[UnknownItem]) -> str:
    lines = "\n".join(f"{u.ref} ({u.category}): {u.question}" for u in unknowns)
    return f"""\
Problem being researched: {problem}
Interviewee: {interviewee}

Open unknowns:
{lines}

Return JSON with: questions (each with unknown_ref, question, follow_ups).
"""


_LEADING = [
    (
        # Any question opening with an auxiliary verb is yes/no ("Do general contractors…?"),
        # except the standard open prompts "Can/Could you walk me through / describe / tell…".
        re.compile(
            r"^\s*(?!(can|could) you (walk|describe|tell|explain|show|give|share|talk|take)\b)"
            r"(do|does|did|would|will|is|are|was|were|can|could|should|shall|have|has|had|may)\b",
            re.IGNORECASE,
        ),
        "Yes/no question: ask about what they actually do instead.",
    ),
    (
        re.compile(r"^\s*(don't|doesn't|isn't|aren't|wouldn't|won't|shouldn't)\b", re.IGNORECASE),
        "Leading: it presumes the answer.",
    ),
    (
        re.compile(
            r"\b(wouldn't it be|would you (use|pay|buy|like)|how much would you pay|"
            r"if (we|there was|you had) (a|an|built)|our (product|tool|app|platform|solution))",
            re.IGNORECASE,
        ),
        "Pitches or asks about a hypothetical product.",
    ),
    (
        re.compile(
            r"\b(how (painful|frustrating|annoying|bad)|don't you (hate|find))\b", re.IGNORECASE
        ),
        "Assumes the problem exists.",
    ),
]


def question_flags(question: str) -> list[str]:
    """Deterministic checks shown next to each question (PRD §22: learn, don't lead)."""
    flags = [msg for pattern, msg in _LEADING if pattern.search(question)]
    if question.count("?") > 1:
        flags.append("Asks several things at once.")
    return list(dict.fromkeys(flags))


# ---------- extraction (PRD §21) ----------

EXTRACT_SYSTEM = """\
You read a founder's notes from a customer interview and extract what the CUSTOMER said.
Rules:
1. Use ONLY the notes. Every "quote" must be copied EXACTLY from the notes, word for word (a
   short span, under 30 words). If the notes don't cover a field, leave value and quote empty.
2. Do not include the founder's own opinions, plans or ideas as customer statements.
3. Fields: problem (what is painful), workflow (how it's solved today), frequency, cost (time
   or money), alternatives (other tools, people or workarounds), trigger (when it becomes
   urgent), buyer (who pays), decision_process (who decides and how), objections (doubts or
   reasons not to change), desired_solution (what they say they want), willingness_to_pay
   (strong / some / low / none / unknown, as in their words).
4. answered_unknowns: for each open unknown (U1, U2…) the notes clearly answer, give its ref,
   a one-sentence answer, and the exact quote. Skip unknowns the notes don't answer.
"""


class AnsweredUnknown(BaseModel):
    unknown_ref: str
    answer: str = Field(min_length=1, max_length=400)
    quote: str = Field(min_length=1)


class InterviewExtraction(BaseModel):
    problem: QuotedText = QuotedText()
    workflow: QuotedText = QuotedText()
    frequency: QuotedText = QuotedText()
    cost: QuotedText = QuotedText()
    alternatives: QuotedText = QuotedText()
    trigger: QuotedText = QuotedText()
    buyer: QuotedText = QuotedText()
    decision_process: QuotedText = QuotedText()
    objections: QuotedText = QuotedText()
    desired_solution: QuotedText = QuotedText()
    willingness_to_pay: QuotedWillingness = QuotedWillingness()
    answered_unknowns: list[AnsweredUnknown] = Field(default_factory=list, max_length=12)


_NON_ANSWER = re.compile(
    r"^\W*((is |was )?not (clearly )?(provided|mentioned|discussed|covered|stated|said|answered|"
    r"specified|given|addressed|clear|known|available)|(the notes )?(do not|don't|does not|doesn't)"
    r" (say|mention|specify|cover|address)|no (clear )?(information|answer|mention|data|details)|"
    r"n/?a|none|unknown|unclear)\b",
    re.IGNORECASE,
)
MIN_QUOTE_CHARS = 8


def is_non_answer(answer: str, quote: str) -> bool:
    """Small models fill `answered_unknowns` for unknowns the notes don't cover ("Not provided
    in the notes.", quote "'"). Those aren't answers, so they're skipped rather than reported
    as dropped quotes."""
    return bool(_NON_ANSWER.match(answer)) or len(re.sub(r"\W", "", quote)) < MIN_QUOTE_CHARS


FIELDS: list[tuple[str, str]] = [
    ("problem", "Problem"),
    ("workflow", "Workflow today"),
    ("frequency", "Frequency"),
    ("cost", "Cost"),
    ("alternatives", "Alternatives"),
    ("trigger", "Trigger"),
    ("buyer", "Buyer"),
    ("decision_process", "Decision process"),
    ("objections", "Objections"),
    ("desired_solution", "Desired solution"),
]


def build_extract_prompt(notes: str, unknowns: list[UnknownItem]) -> str:
    lines = "\n".join(f"{u.ref}: {u.question}" for u in unknowns) or "(none)"
    return f"""\
Open unknowns:
{lines}

Interview notes (between the markers):
<<<
{notes}
>>>

Return JSON with: problem, workflow, frequency, cost, alternatives, trigger, buyer,
decision_process, objections, desired_solution, willingness_to_pay, answered_unknowns.
"""
