from enum import StrEnum


class ProviderName(StrEnum):
    LOCAL = "local"  # Ollama
    GEMINI = "gemini"


class TaskType(StrEnum):
    # Light, single-input tasks — fine for a local 8B model.
    CLASSIFY_EVIDENCE = "classify_evidence"
    EXTRACT_FIELDS = "extract_fields"
    CLASSIFY_RESPONSE = "classify_response"
    SUMMARIZE_SHORT = "summarize_short"
    DRAFT_OUTREACH = "draft_outreach"
    # Multi-source reasoning / long context — Gemini.
    ANALYZE_IDEA = "analyze_idea"
    GENERATE_ICPS = "generate_icps"
    SYNTHESIZE_EVIDENCE = "synthesize_evidence"
    ANALYZE_COMPETITORS = "analyze_competitors"
    VALIDATION_REPORT = "validation_report"


DEFAULT_ROUTES: dict[TaskType, ProviderName] = {
    TaskType.CLASSIFY_EVIDENCE: ProviderName.LOCAL,
    TaskType.EXTRACT_FIELDS: ProviderName.LOCAL,
    TaskType.CLASSIFY_RESPONSE: ProviderName.LOCAL,
    TaskType.SUMMARIZE_SHORT: ProviderName.LOCAL,
    TaskType.DRAFT_OUTREACH: ProviderName.LOCAL,
    TaskType.ANALYZE_IDEA: ProviderName.GEMINI,
    TaskType.GENERATE_ICPS: ProviderName.GEMINI,
    TaskType.SYNTHESIZE_EVIDENCE: ProviderName.GEMINI,
    TaskType.ANALYZE_COMPETITORS: ProviderName.GEMINI,
    TaskType.VALIDATION_REPORT: ProviderName.GEMINI,
}
