# Developer Setup & Workflow Guide (`development.md`)

---

## 1. Prerequisites

- **Git** `2.40+`
- **Python** `3.12+` (for native backend development & tests)
- **Node.js** `20 LTS+` and **npm** `10+` (for native frontend development & tests)
- **Docker Desktop / Docker Engine** with Compose v2 (for full multi-service local stack)

---

## 2. Environment Configuration

Copy the templates and review settings:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

### Labeled Development Fixture Mode
When environmental credentials (`AIR_QUALITY_API_KEY`, `WEATHER_API_KEY`) are not yet configured on a developer laptop:
- Set `AIR_QUALITY_PROVIDER=fixture` and `WEATHER_PROVIDER=fixture` in `backend/.env` (only permitted when `APP_ENV=development` or `APP_ENV=test`).
- Every fixture reading sets `is_development_fixture: true` and renders a visible **"Development Fixture Data"** banner in the UI so synthetic test readings are never confused with real air quality measurements.

---

## 3. Running Locally

### Full Stack via Docker Compose
```bash
docker compose up --build
docker compose exec backend alembic upgrade head
```

### Native Backend (`backend/`)
```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS / Linux:
# source .venv/bin/activate

pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

### Native Frontend (`frontend/`)
```bash
cd frontend
npm install
npm run dev
```

---

## 4. Quality Gates (Run Before Every Commit)

```bash
# Backend lint, typecheck, and unit tests
cd backend
ruff check app tests
mypy app
pytest

# Frontend lint, strict TypeScript check, and unit tests
cd ../frontend
npm run lint
npm run typecheck
npm run test
```

Consult [`AGENTS.md`](../AGENTS.md) and [`.agents/skills/`](../.agents/skills/) before implementing domain changes.

### Selector styling

Single-value dropdowns share chevron styling in
[`globals.css`](../frontend/src/app/globals.css): a vertically centered, inset icon
and reserved text padding, including dark mode and right-to-left layouts. Keep
native `<select>` elements, labels, and keyboard behavior; multiple/listbox
selectors are excluded, and forced-colors mode restores the browser arrow.
With the frontend running, use `npx playwright test select-layout.spec.ts`
from `frontend/` to check desktop/mobile alignment and keyboard selection.

---

## 5. Gemini Assistant and Trusted Knowledge

1. Configure backend-only `GEMINI_API_KEY` in `backend/.env`; never put it in `NEXT_PUBLIC_*`.
   `GEMINI_MODEL` defaults to `gemini-2.5-flash` and is configurable. No OpenAI account or SDK is needed.
2. Start PostgreSQL with PostGIS/pgvector and Redis using the existing Compose stack.
3. From `backend/`, run `alembic upgrade head`, then `python -m scripts.ingest_knowledge`.
   The CLI reads the reviewed WHO/EPA/NCDC editorial summaries in
   [`knowledge_sources.json`](../backend/scripts/knowledge_sources.json), generates
   `gemini-embedding-001` embeddings with 768 dimensions, and records ingestion jobs.
   Repeated ingestion reuses unchanged chunks. An operator can supply a reviewed local JSON
   manifest with the same schema; the CLI does not download user-provided URLs.
   The worker task `app.workers.knowledge_tasks.ingest_curated_knowledge` ingests the same corpus.
4. Sign in, open `/dashboard/assistant`, select a city and AQI standard, and explicitly consent
   to send the minimized question to Google Gemini. Household preference sharing is a separate,
   per-request opt-in. Avoid entering identifying, clinical or confidential information.
5. History follows the existing `save_chat_history` setting. Disabling it stops persistence and
   prior-turn context reuse; existing history remains until explicitly deleted. Chat history is
   included in account export and removed by account erasure.

`AI_REQUESTS_PER_MINUTE`, `AI_DAILY_TOKEN_BUDGET` and `AI_MAX_OUTPUT_TOKENS` bound usage.
The daily Redis quota conservatively reserves UTF-8 input bytes plus the output-token limit,
including retries; it is deliberately not a billing report. Redis quota failures prevent model
calls. Missing credentials, missing evidence, provider outages and rejected output produce
explicitly labeled deterministic safety guidance, not fake Gemini responses.

Run Phase 4 checks from `backend/`:

```powershell
python -m ruff check app scripts tests/ai_evaluations tests/integration/test_assistant_flows.py tests/unit/test_gemini_gateway.py
python -m mypy app
python -m pytest tests/ai_evaluations tests/integration/test_assistant_flows.py tests/unit/test_gemini_gateway.py
```

From `frontend/`, run `npm run lint`, `npm run typecheck`, `npm run test` and `npm run build`.
For the focused browser test, run `npx playwright install chromium`, start the built frontend
with `npm run start`, then run `npx playwright test` in another terminal. Use
`PLAYWRIGHT_BASE_URL` when the frontend is not on port 3000. The assistant browser scenario
mocks API responses with test-only data; backend integration tests exercise the real API.
Automated tests mock Gemini and use SQLite for persistence/migration checks; they do not prove
live Gemini credentials, PostgreSQL vector ranking or Redis connectivity. Validate those against
configured services before claiming production readiness.
