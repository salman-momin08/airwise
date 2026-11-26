# ADR 0002: Consolidate Relational, Geospatial (PostGIS), and Vector (pgvector) Storage on PostgreSQL

- **Status:** Accepted
- **Date:** 2026-11-19

## Context
AirWise AI requires ACID relational storage (users, sessions, routines, alerts, communities, audit logs), spatial radius/nearest-station queries for hyperlocal air quality, and semantic vector similarity search paired with structured metadata filters (jurisdiction, freshness, trust level) for environmental RAG.

## Decision
Use **PostgreSQL 16+** as the single primary database with **`postgis`** for spatial operations (`GEOGRAPHY(POINT, 4326)`) and **`pgvector`** for knowledge-chunk embeddings, supplemented by **Redis** for low-latency caching, rate limiting, and Celery task brokering.

## Consequences
- **Positive:** Eliminates dual-write consistency bugs between a separate vector store and relational metadata; enables hybrid SQL + `pgvector` HNSW queries filtered atomically by `trust_classification` and `last_reviewed_date`; simplifies backups, point-in-time recovery, and zero-cost cloud deployment (Neon and Supabase free tiers natively support PostgreSQL 16 + PostGIS + pgvector alongside Vercel).
- **Mitigation:** Partition high-volume `air_quality_measurements` by month and index `knowledge_chunks` with HNSW cosine distance.
