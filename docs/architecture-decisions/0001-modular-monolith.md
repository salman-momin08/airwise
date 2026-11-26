# ADR 0001: Adopt a Modular Monolith Backend Architecture

- **Status:** Accepted
- **Date:** 2026-11-19

## Context
AirWise AI spans authentication, geospatial locations, multi-provider air quality ingestion, RAG knowledge search, conversational GenAI orchestration, routine planning, deterministic impact math, smart alerts, and neighborhood communities. Splitting these into distributed microservices on day one would introduce network hops, distributed transactions, duplicated auth/schema boilerplate, and high operational overhead without proportional scale benefits.

## Decision
Implement the backend as a **strictly layered Python FastAPI modular monolith** (`backend/app/`), paired with stateless `Celery` worker and `Celery Beat` scheduler processes built from the same container image and domain codebase.

## Consequences
- **Positive:** Shared typed Pydantic/SQLAlchemy models, ACID transactions across user actions and impact records, zero internal RPC serialization latency on chat orchestration, simple `docker compose up --build` developer experience, and independent horizontal scaling of HTTP pods vs background workers.
- **Guardrail:** Enforce strict unidirectional module imports (`api -> services -> repositories -> models`) so high-throughput subsystems (such as ingestion or AI gateway) can be extracted later if workload profiles diverge.
