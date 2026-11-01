"""Shared builders for analysis tests: canned LLM outputs and a fake-backed router."""

from app.llm.fake import FakeProvider
from app.llm.router import LLMRouter
from app.llm.tasks import ProviderName


def rating(n: int) -> dict:
    return {"rating": n, "rationale": f"rated {n}"}


def ratings(pain=3, pay=3, reach=3, freq=3, size=3) -> dict:
    return {
        "pain_likelihood": rating(pain),
        "ability_to_pay": rating(pay),
        "reachability": rating(reach),
        "frequency_urgency": rating(freq),
        "segment_size": rating(size),
    }


def analysis_output(problem: str = "PMs lose hours to manual reports", n_unknowns: int = 3) -> dict:
    return {
        "hypothesis": {
            "problem": problem,
            "users": "Project managers",
            "buyer": "Likely operations directors",
            "decision_maker": "Likely the owner",
            "economic_value": "Less reporting labor",
            "geography": "United States",
            "industry": "Construction",
        },
        "unknowns": [
            {
                "question": f"How often does X happen? ({i})",
                "category": "frequency",
                "priority": "high",
            }
            for i in range(n_unknowns)
        ],
    }


def icp(name: str, **rating_kwargs) -> dict:
    return {
        "name": name,
        "company_type": "General contractors",
        "size_min": 50,
        "size_max": 500,
        "geography": "United States",
        "signals": ["posts project coordinator jobs"],
        "user_roles": ["Project manager"],
        "buyer_roles": ["Operations director"],
        "ratings": ratings(**rating_kwargs),
    }


def icps_output(*icps: dict) -> dict:
    return {"icps": list(icps) or [icp("Mid-size GCs")]}


def make_router() -> tuple[LLMRouter, FakeProvider, FakeProvider]:
    local, gemini = FakeProvider("local"), FakeProvider("gemini")

    async def no_sleep(_: float) -> None:
        return None

    router = LLMRouter({ProviderName.LOCAL: local, ProviderName.GEMINI: gemini}, sleep=no_sleep)
    return router, local, gemini
