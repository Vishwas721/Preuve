# ADR 0002 — Hybrid local + Gemini LLM strategy

- **Status:** accepted
- **Date:** 2026-10-06

## Context
No paid LLM APIs. Available: a local `llama3:8b` via Ollama (8K context, Q4) and a Gemini free-tier
API key. An 8B model handles short classification/extraction but is unreliable for multi-source
synthesis and is prone to unsupported claims — the opposite of what an evidence product needs.

## Decision
- One `LLMProvider` interface; Ollama, Gemini and Fake implementations.
- A task router assigns each `TaskType` a default provider (light tasks → local, synthesis → Gemini).
- All structured output is validated against Pydantic schemas; invalid output is retried, then
  escalated local → Gemini.
- Model names are configuration, so the local model can be swapped without code changes.
- Update 2026-11-01: benchmarked with `app/scripts/llm_bench.py` (11 Preuve-style tasks x 2):
  `llama3:8b` 14/22, `llama3.1:8b` 16/22, `qwen2.5:7b` 18/22 (only misses: an under-specified
  extraction prompt). Default is now `qwen2.5:7b`. Gemini uses a 3-model fallback chain
  (`3.8-flash -> 3.6-flash -> 2.5-flash`) with per-model cooldown.

## Consequences
- Free to run; most high-volume calls stay local.
- Gemini free-tier rate limits require backoff and keeping synthesis calls few and batched.
- Free-tier Gemini data may be used by Google; private correspondence defaults to local processing.
