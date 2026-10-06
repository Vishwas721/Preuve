"""Check that each real LLM provider answers a structured request.

Run: uv run python -m app.scripts.llm_smoke
"""

import asyncio
import time

from pydantic import BaseModel

from app.llm.base import LLMError
from app.llm.router import get_llm_router
from app.llm.tasks import ProviderName

PROMPT = (
    "A prospect replied: 'We have this problem every week. Our PMs spend about 4-5 hours "
    "creating reports in Excel with photos from WhatsApp.' Does the reply confirm the "
    "problem, and how often does it happen?"
)


class ReplySignal(BaseModel):
    problem_confirmed: bool
    frequency: str | None
    current_tools: list[str]


async def main() -> None:
    providers = get_llm_router().providers
    for name in (ProviderName.LOCAL, ProviderName.GEMINI):
        provider = providers[name]
        started = time.perf_counter()
        try:
            result = await provider.generate_structured(PROMPT, ReplySignal)
        except LLMError as exc:
            print(f"[{name}] FAILED: {exc}")
            continue
        print(f"[{name}] ok in {time.perf_counter() - started:.1f}s -> {result.model_dump()}")


if __name__ == "__main__":
    asyncio.run(main())
