# Cloud Deployment Manifests (`infrastructure/deployment/`)

Primary cloud deployment target: **Zero-Cost Vercel Hosting (`vercel.json` + `api/index.py`) + Free Managed Serverless PostgreSQL 16 (`Neon` / `Supabase` with PostGIS + pgvector) + Free Serverless Redis (`Upstash`)**.

## Vercel Zero-Cost Runtime Profile

| Component | Vercel / Managed Resource | Free-Tier Scaling & Cost Profile | Notes |
| :--- | :---: | :--- | :--- |
| `frontend/` | Vercel Next.js App Router | Auto-scaled Edge/Serverless (`$0` Hobby) | RSC, static assets, client interactive leaves |
| `api/index.py` | Vercel Python Serverless Runtime | On-demand ephemeral functions (`$0` Hobby) | Same-origin `/api/v1/*`, `/health/*`, `/metrics` |
| `crons` | Vercel Cron Jobs (`vercel.json`) | Daily scheduled trigger (`30 2 * * *` UTC) | Calls `/api/v1/system/cron/daily-maintenance` with `CRON_SECRET` |
| `postgres` | Neon / Supabase Free Tier | Serverless Postgres 16 + Connection Pooler | `postgis`, `vector`, `citext`, `uuid-ossp` enabled |
| `redis` | Upstash Serverless Redis Free Tier | Pay-per-request free quota (`rediss://`) | AQI cache, sliding-window rate limits, alert dedup |

## Setup Steps on Vercel (Free Tier)

1. Provision a free **Neon** or **Supabase** PostgreSQL 16 database and run [`infrastructure/docker/postgres/init-extensions.sql`](../docker/postgres/init-extensions.sql) once to enable `uuid-ossp`, `citext`, `postgis`, and `vector`.
2. Provision a free **Upstash** Redis database and copy its `rediss://` URL.
3. Import the `salman-momin08/airwise` repository into **Vercel** (keep Root Directory as `./` so `vercel.json` builds `frontend/` and mounts `api/index.py`).
4. Configure Vercel Environment Variables:
   - `APP_ENV=production`
   - `DEBUG=false`
   - `AUTH_COOKIE_SECURE=true`
   - `AUTH_SECRET_KEY=<64-byte-random-secret>`
   - `DATABASE_URL=<neon-or-supabase-pooled-postgresql+asyncpg-url>`
   - `DATABASE_SERVERLESS_POOL=true`
   - `REDIS_URL=<upstash-rediss-url>`
   - `CRON_SECRET=<32-byte-random-secret>`
   - `NEXT_PUBLIC_API_BASE_URL=/api/v1`
   - `AIR_QUALITY_PROVIDER=openaq` (plus `AIR_QUALITY_API_KEY`, `WEATHER_API_KEY`, `OPENAI_API_KEY`)
5. Run `alembic upgrade head` via `.github/workflows/deploy.yml` (or locally pointing at `DATABASE_URL`) and deploy.
