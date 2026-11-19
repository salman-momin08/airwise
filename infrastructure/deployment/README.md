# Cloud Deployment Manifests (`infrastructure/deployment/`)

Reference deployment target: **AWS ECS Fargate + RDS PostgreSQL 16 (PostGIS + pgvector) + ElastiCache Redis 7**.

## Service Sizing Baseline

| Service | vCPU / Memory | Scaling Policy | Notes |
| :--- | :---: | :--- | :--- |
| `airwise-frontend` | `0.5 vCPU / 1 GB` | Target CPU 65% (min 2, max 10) | Stateless Next.js standalone server |
| `airwise-backend` | `1.0 vCPU / 2 GB` | Target ALB ReqCount / CPU 60% (min 2, max 12) | Stateless FastAPI + SSE |
| `airwise-worker` | `1.0 vCPU / 2 GB` | Redis queue depth (min 2, max 8) | Celery ingestion & alert evaluator |
| `airwise-scheduler` | `0.25 vCPU / 0.5 GB` | Fixed `desiredCount = 1` | Singleton Celery Beat leader |
