# ADR 0003: Hybrid Deterministic + GenAI Recommendation & Impact Architecture

- **Status:** Accepted
- **Date:** 2026-11-19

## Context
Pure LLM systems frequently hallucinate numerical emissions savings, conflate AQI standards, or suggest unsafe outdoor exercise during severe winter smog because cycling is "eco-friendly." Conversely, purely rule-based systems struggle to synthesize nuanced household schedules and accessible explanations.

## Decision
Separate numerical/safety authority from natural-language synthesis:
1. **Deterministic Python Engines** own AQI sub-index computation, environmental safety overrides (exposure safety > sustainability), and all impact calculations (transport CO2e, household kWh, CADR/ACH filtration, relative exposure).
2. **RAG + LLM Orchestration** retrieves authoritative public-health evidence and personalizes explanations and daily routines strictly within the bounds set by deterministic outputs, verified by post-generation Pydantic and numerical/citation checks.

## Consequences
- **Positive:** 100% reproducible, unit-tested calculations; zero LLM math drift; graceful degradation to deterministic safety guidance even if external LLM APIs experience an outage.
- **Trade-off:** Slightly higher orchestration engineering rigor (schema contracts + post-LLM verification step), justified by environmental and health-adjacent trustworthiness requirements.
