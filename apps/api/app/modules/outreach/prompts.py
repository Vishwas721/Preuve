"""Prompt and output schema for `draft_outreach` (PRD §17).

The model only sees what's in the prompt: the problem being researched, the sender, the
recipient, their company and the company's verified public evidence. Evidence is referenced by
short refs (E1, E2…) that are verified and mapped back to evidence ids.
"""

from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.llm.guardrails import Claim

SYSTEM = """\
You write short, honest, research-oriented cold emails for a founder who is validating a
problem before building anything. Rules:
1. Use ONLY the facts given in the prompt. Never invent facts, numbers, quotes, names or links.
2. The product does NOT exist. Never say or imply it exists. No pitch, demo, pricing, trial or
   sign-up. No hype words, no exaggeration, no flattery.
3. Address the recipient by first name. Say in one sentence why you're writing to them in
   particular, based on the evidence given.
4. State the research purpose plainly and ask exactly ONE small, easy-to-answer question.
5. Under 120 words. Plain text. Sign off with the sender's name. Do not add an unsubscribe line
   or a signature block; those are added automatically.
6. Only cite evidence refs that appear in the prompt (E1, E2, ...). If no evidence is relevant,
   cite none and say nothing specific about the company beyond its name and description.
7. `why_selected` explains to the founder (not the recipient) why this person was chosen.
   Label each statement "fact" (directly stated in cited evidence; cite refs), "inference"
   (drawn from cited evidence; cite refs) or "assumption" (not supported; no refs).
   Return an empty list if there's nothing to say.
"""


class OutreachDraft(BaseModel):
    subject: str = Field(min_length=1, max_length=120, description="Short, specific, not salesy.")
    body: str = Field(min_length=1, description="The email body, without footer.")
    cited_refs: list[str] = Field(
        default_factory=list, description="Evidence refs (E1…) the body relies on."
    )
    why_selected: list[Claim] = Field(default_factory=list, max_length=3)


@dataclass(frozen=True)
class EvidenceItem:
    ref: str
    quote: str
    url: str


@dataclass(frozen=True)
class DraftContext:
    problem: str
    purpose: str
    sender_name: str
    contact_name: str
    contact_role: str
    company_name: str
    company_description: str
    evidence: tuple[EvidenceItem, ...]


def build_prompt(ctx: DraftContext) -> str:
    if ctx.evidence:
        ev = "\n".join(f'{e.ref}: "{e.quote}" (source: {e.url})' for e in ctx.evidence)
    else:
        ev = "(none)"
    return f"""\
Problem being researched: {ctx.problem}
Research purpose: {ctx.purpose}
Sender: {ctx.sender_name}

Recipient: {ctx.contact_name}, {ctx.contact_role} at {ctx.company_name}
Company description: {ctx.company_description}

Verified public evidence about this company:
{ev}

Write the email. Return JSON with: subject, body, cited_refs, why_selected.
"""
