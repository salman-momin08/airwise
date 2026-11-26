# ADR 0006: Zero-Cost Cloud Hosting on Vercel + Managed Serverless Postgres & Redis

- **Status:** Accepted (Supersedes AWS ECS Fargate / RDS / ElastiCache reference hosting)
- **Date:** 2026-11-24

## Context
AirWise AI originally documented a reference cloud deployment on AWS ECS Fargate + Amazon RDS PostgreSQL + Amazon ElastiCache Redis + CloudFront/ALB. However, always-on VPC load balancers, NAT gateways, Fargate tasks, RDS instances, and ElastiCache nodes incur continuous monthly infrastructure costs even at low traffic. The project requires a **zero-cost (`$0/month`) production-capable hosting architecture** without sacrificing any of the 15 non-negotiable security, privacy, scientific, or architectural invariants.

## Decision
Standardize cloud hosting on **Vercel's free Hobby tier** paired with free-tier serverless stateful backing services:

1. **Unified Same-Origin Edge & Compute on Vercel (`vercel.json`):**
   - **Frontend (`frontend/`):** Deployed natively as a Next.js App Router project on Vercel Edge/Serverless.
   - **Backend (`api/index.py` -> `backend/app/main.py`):** Deployed in the same Vercel project via the Vercel Python Serverless Runtime, with same-origin rewrites for `/api/v1/*`, `/health/*`, and `/metrics`.
   - Same-origin routing makes `HttpOnly`, `Secure`, `SameSite=Lax` session cookies and double-submit `X-CSRF-Token` headers work seamlessly without third-party cookie blocking.
2. **Serverless PostgreSQL 16 (`Neon` or `Supabase` Free Tier):**
   - Provides native `postgis`, `vector` (`pgvector`), `citext`, and `uuid-ossp` extensions at zero cost.
   - SQLAlchemy `AsyncEngine` automatically switches to `NullPool` when running in serverless mode (`VERCEL=1` or `DATABASE_SERVERLESS_POOL=true`) so ephemeral function invocations delegate connection pooling cleanly to Neon/Supabase's transaction pooler.
3. **Serverless Redis (`Upstash Redis` Free Tier):**
   - Provides TLS-encrypted (`rediss://`) Redis for AQI caching, sliding-window rate limiting, and alert cooldown deduplication.
4. **Scheduled Background Execution (`Vercel Cron` + GitHub Actions Scheduler):**
   - Daily maintenance (session retention cleanup, environmental refresh, alert evaluation) is triggered via authenticated `GET /api/v1/system/cron/daily-maintenance` using Vercel's `CRON_SECRET` bearer header (`hmac.compare_digest`), with optional higher-frequency polling via free GitHub Actions scheduled workflows or local Docker Celery Beat.
5. **Transactional Email (`Resend` Free Tier / Console):**
   - Uses `EMAIL_PROVIDER=resend` (free tier) or `console` in development, replacing paid AWS SES.

## Consequences
- **Positive:** `$0/month` hosting cost; automatic HTTPS/TLS, preview deployments per PR, zero VPC/ALB maintenance, and native same-origin cookie security.
- **Portability Preserved:** `docker-compose.yml`, `Dockerfile`s, and Celery workers remain intact for local development and optional self-hosted container deployments.
