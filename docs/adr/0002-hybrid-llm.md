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
- Model names are configuration, so the local model can be upgraded (e.g. `llama3.1:8b`,
  `qwen2.5:7b`) without code changes.

## Consequences
- Free to run; most high-volume calls stay local.
- Gemini free-tier rate limits require backoff and keeping synthesis calls few and batched.
- Free-tier Gemini data may be used by Google; private correspondence defaults to local processing.
