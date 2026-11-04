"""Prompt and output schema for `classify_response` (PRD §20).

Every field the model fills carries the customer's exact words. Labels have precise definitions
(the Phase 0 benchmark showed vague labels drift on an 8B model), and "unclear" is always
allowed. The recommended action is computed from the labels, not asked of the model.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class Sentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class YesNo(StrEnum):
    YES = "yes"
    NO = "no"
    UNCLEAR = "unclear"


class Level(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCLEAR = "unclear"


class Willingness(StrEnum):
    UNKNOWN = "unknown"
    NONE = "none"
    LOW = "low"
    SOME = "some"
    STRONG = "strong"


class QuotedText(BaseModel):
    value: str = Field(default="", description="Short summary, e.g. 'weekly'. Empty if not said.")
    quote: str = Field(default="", description="The customer's exact words. Empty if not said.")


class QuotedYesNo(BaseModel):
    value: YesNo = YesNo.UNCLEAR
    quote: str = ""


class QuotedLevel(BaseModel):
    value: Level = Level.UNCLEAR
    quote: str = ""


class QuotedWillingness(BaseModel):
    value: Willingness = Willingness.UNKNOWN
    quote: str = ""


class ResponseClassification(BaseModel):
    sentiment: Sentiment = Sentiment.NEUTRAL
    problem_confirmed: QuotedYesNo = QuotedYesNo()
    pain: QuotedText = QuotedText()
    frequency: QuotedText = QuotedText()
    current_solution: QuotedText = QuotedText()
    time_or_cost: QuotedText = QuotedText()
    severity: QuotedLevel = QuotedLevel()
    solution_satisfaction: QuotedLevel = QuotedLevel()
    interest: QuotedLevel = QuotedLevel()
    willingness_to_pay: QuotedWillingness = QuotedWillingness()


SYSTEM = """\
You read one reply to a founder's research email and extract what the customer actually said.
Rules:
1. Use ONLY the reply text. Never infer facts the reply doesn't state.
2. Every "quote" must be copied EXACTLY from the reply, word for word (a short span, under 30
   words). If the reply doesn't say it, leave value and quote empty or "unclear".
3. Labels:
   - sentiment: positive = friendly and engaged; negative = annoyed, dismissive or refusing;
     neutral = anything else (short, polite, factual).
   - problem_confirmed: yes = they say they have this problem; no = they say they don't, or it
     isn't a problem for them; unclear = they don't say.
   - pain: what they say is painful, in their words.
   - frequency: how often it happens (e.g. "weekly", "every project"), only if stated.
   - current_solution: what they use or do today (tools, people, spreadsheets), only if stated.
   - time_or_cost: time or money it takes, only if stated (e.g. "4-5 hours a week").
   - severity: high = they call it a big/serious/constant problem; medium = an annoyance they
     live with; low = minor; unclear = not said.
   - solution_satisfaction: how happy they are with what they use today (high/medium/low);
     unclear if not said.
   - interest: high = asks to talk, see more, or offers time; medium = open but noncommittal;
     low = not interested; unclear = not said.
   - willingness_to_pay: strong = says they'd pay or have budget; some = open to paying;
     low = reluctant; none = says they won't pay; unknown = money not mentioned.
4. Do not flatter the founder's idea or add advice.
"""


def build_prompt(reply: str, original_subject: str | None) -> str:
    context = f'It answers an email titled "{original_subject}".\n' if original_subject else ""
    return f"""\
{context}Reply text (between the markers):
<<<
{reply}
>>>

Return JSON with: sentiment, problem_confirmed, pain, frequency, current_solution,
time_or_cost, severity, solution_satisfaction, interest, willingness_to_pay.
"""
