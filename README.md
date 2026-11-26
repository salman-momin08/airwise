# AirWise AI

> **Breathe Smarter. Live Cleaner. Act Together.**

**AirWise AI is an environmental wellness platform that turns air-quality information into practical, exposure-first daily decisions.** It combines environmental-provider data, deterministic safety rules and impact calculators, a grounded conversational assistant, daily planning, alerts, and neighborhood action.

The goal is not merely to answer **"What is the AQI?"** It is to help answer **"What can I safely do today, why does it help, and what are the limits of that advice?"**

**Project status:** The repository contains frontend pages, backend APIs, migrations, workers, and automated tests across the product modules below. This is a production-oriented implementation, **not a claim of production certification**. Live integrations, deployment limits, accessibility, performance, and the [15-point Definition of Done](./docs/planning.md#5-15-point-definition-of-done-mandatory-gate) must be validated for the intended environment.

**Safety notice:** AirWise provides environmental guidance, not medical diagnosis, treatment, or guaranteed health outcomes. Synthetic development data is explicitly labeled. Missing data remains unavailable; estimates are not measurements.

---

## Contents

- [1. Problem statement](#1-problem-statement)
- [2. The solution AirWise provides](#2-the-solution-airwise-provides)
- [3. Who it serves and the end-to-end journey](#3-who-it-serves-and-the-end-to-end-journey)
- [4. Product modules and current scope](#4-product-modules-and-current-scope)
- [5. System architecture](#5-system-architecture)
- [6. Environmental data and AQI methodology](#6-environmental-data-and-aqi-methodology)
- [7. AirWise Copilot and trusted RAG](#7-airwise-copilot-and-trusted-rag)
- [8. Deterministic impact estimates](#8-deterministic-impact-estimates)
- [9. Security, privacy, and user control](#9-security-privacy-and-user-control)
- [10. Repository structure](#10-repository-structure)
- [11. Local setup](#11-local-setup)
- [12. Configuration and live integrations](#12-configuration-and-live-integrations)
- [13. API overview](#13-api-overview)
- [14. Testing and quality gates](#14-testing-and-quality-gates)
- [15. Deployment and operations](#15-deployment-and-operations)
- [16. Troubleshooting](#16-troubleshooting)
- [17. Roadmap and documentation](#17-roadmap-and-documentation)
- [18. Contributing and license](#18-contributing-and-license)

## 1. Problem statement

Urban air pollution and seasonal winter smog create a daily decision problem for individuals and households. A pollution reading alone does not tell a parent how to plan outdoor play, a commuter how to balance exposure and transport choices, or a caregiver how to respond to deteriorating conditions.

The problem has several connected parts:

| Gap | Why it matters |
| :--- | :--- |
| **Numbers without actionable context** | AQI categories do not directly explain which routines to change, which alternatives are feasible, or when guidance is uncertain. |
| **Fragmented information** | Air quality, weather, indoor filtration advice, commute comparisons, and community initiatives often live in separate tools. |
| **Incompatible AQI standards** | US EPA AQI and India NAQI use different breakpoints, averaging rules, and category names. Treating them as interchangeable can mislead users. |
| **Incomplete or stale observations** | A missing pollutant, old station reading, or regional model output must not masquerade as a current street-level measurement. |
| **Conflicting safety and sustainability goals** | A low-carbon commute is not automatically a low-exposure commute. Outdoor walking or cycling may be inappropriate during severe pollution. |
| **Unreliable AI explanations** | A general-purpose chatbot can invent local readings, calculate unsupported savings, or supply unverifiable citations. |
| **Privacy and control concerns** | Useful personalization should not require unnecessary precise location sharing, exposure of household information, or automatic schedule changes. |

**The core problem:** People need trustworthy help translating environmental conditions into safer, realistic daily actions without confusing observations, forecasts, estimates, and general guidance.

## 2. The solution AirWise provides

AirWise brings the decision process into one application:

1. **Understand conditions:** Select a supported city or save a consented location; inspect air quality, pollutants, source, timestamps, and the selected AQI standard.
2. **Apply safety rules:** Evaluate exposure concerns before optimizing carbon savings or convenience.
3. **Explain options:** Use backend tools and reviewed environmental guidance to answer questions with explicit evidence and limitations.
4. **Plan and compare:** Generate a routine, compare transport or household alternatives, and inspect deterministic estimates.
5. **Keep the user in control:** Edit and explicitly save plans, configure alerts, choose what to share with the assistant, and manage stored history.
6. **Support collective action:** Join neighborhood challenges and view aggregate participation without pretending voluntary actions measure a change in city-wide AQI.

### Three separate impact dimensions

| Dimension | What AirWise helps evaluate | What it does not claim |
| :--- | :--- | :--- |
| **Personal exposure reduction** | Reducing time or estimated concentration in polluted microenvironments; choosing safer timing and indoor alternatives. | Exact inhaled dose, disease prevention, or a measured indoor reading inferred from outdoor AQI. |
| **Emission reduction** | Estimated transport and electricity CO2e differences using explicit factors and assumptions. | That a lower-emission option is always safer to use today. |
| **Community impact** | Voluntary participation, moderated initiatives, and aggregate action estimates. | That a household pledge or challenge measurably lowers city-wide ambient AQI. |

**Decision priority:** Exposure safety -> schedule constraints -> feasibility -> emission reduction -> cost -> convenience.

For example, when pollution is severe, an outdoor exercise request should lead to a safer alternative and an explanation of uncertainty, not a recommendation to cycle solely because it saves CO2e. If indoor air is not measured, the application must say so.

## 3. Who it serves and the end-to-end journey

| User | Typical need | Relevant experience |
| :--- | :--- | :--- |
| Parents and families | Plan school travel and outdoor activities; understand home filtration options. | Dashboard, routine planner, indoor-air guidance, alerts. |
| Commuters | Compare travel alternatives without conflating exposure and emissions. | Transport comparison, impact estimates, Copilot. |
| Older adults and caregivers | Clear, conservative environmental guidance and simple alerts. | Text-labeled AQI categories, assistant, alert preferences. |
| Students | Understand pollution science and inspect the reasoning behind recommendations. | Learn hub, cited assistant answers, transparent calculators. |
| Community organizers | Coordinate clean-air challenges and moderate local contributions. | Community groups, participation summaries, moderation tools. |

```mermaid
flowchart LR
    Discover["Explore public AQI and learning pages"] --> City["Choose city and AQI standard"]
    City --> Conditions["Inspect conditions, source, and freshness"]
    Conditions --> Account["Register and optionally personalize"]
    Account --> Guidance["Ask Copilot or generate recommendations"]
    Guidance --> Plan["Compare options and edit a daily plan"]
    Plan --> Confirm["Explicitly save or log an action"]
    Confirm --> Follow["Configure alerts and track estimates"]
    Follow --> Community["Join voluntary neighborhood initiatives"]
```

Public environmental pages do not require an account. Account-specific plans, preferences, history, and actions require authentication. Selecting a city remains an alternative to granting browser geolocation.

## 4. Product modules and current scope

The following modules have implementation paths in this repository. Their presence does not mean every live provider or release gate has been verified.

| Module | Capabilities in the repository | Main UI routes |
| :--- | :--- | :--- |
| **Identity and governance** | Email/password registration and login, verification/reset APIs, session inspection/revocation, profile and preference management, export and deletion. | `/login`, `/register`, `/forgot-password`, `/dashboard/settings/*` |
| **Locations** | City/postal-prefix search through a curated gazetteer, saved locations, precision metadata, ownership enforcement. | `/dashboard/settings/locations` |
| **Environmental intelligence** | Current, historical, and forecast AQI; pollutant details; station/GeoJSON APIs; trend and map UI; provenance and fixture labeling. | `/air-quality`, `/air-quality/[city]`, `/dashboard/air-quality` |
| **AirWise Copilot** | Gemini gateway, consent controls, bounded tools, evidence retrieval, validated SSE responses, optional persisted conversation history. | `/dashboard/assistant` |
| **Recommendations and routines** | Exposure-first recommendations, feedback, daily routine generation, editing and persistence. | `/dashboard`, `/dashboard/routine-planner` |
| **Indoor air and transport** | Filtration sizing guidance and deterministic comparisons of transport, energy, and relative exposure. | `/dashboard/indoor-air`, `/dashboard/transport` |
| **Impact and history** | Explicit action logging and estimated impact summaries/history. | `/dashboard/impact`, `/dashboard/history` |
| **Alerts** | Rule management, threshold/forecast/window/digest evaluation, notifications, cooldowns and quiet-hour handling. | `/dashboard/alerts` |
| **Community** | Groups, initiatives, voluntary participation, aggregate summaries, reporting and moderation. | `/dashboard/community`, `/admin/community` |
| **Learning and administration** | Educational pages; administrative users, data-source governance, knowledge governance, AI monitoring and audit views. | `/learn`, `/learn/[slug]`, `/admin/*` |

### Important implementation boundaries

- **Live AQI:** OpenAQ and OpenWeather adapters exist. CPCB is a regional adapter interface, not a turnkey configured government-feed integration.
- **Weather:** OpenWeather, Open-Meteo, and explicitly labeled fixture adapters exist. Availability depends on the selected provider and its response.
- **Locations:** The bundled city catalog includes Delhi, Gurugram, Noida, Bengaluru, Mumbai, Chennai, Kolkata, Hyderabad, Pune, and Lucknow. Do not assume global city or address lookup merely because geocoding configuration fields exist.
- **Google sign-in:** OAuth scaffolding/status exists, but the Google token exchange is a stub. Adding credentials alone does not complete social login.
- **Notifications:** In-app and email delivery paths exist. Web push is represented as an unconfigured channel; it is not a working push subscription/delivery integration.
- **Indoor sensors:** Filtration estimates are not an indoor sensor connection. Without an actual measurement, indoor air quality remains **unmeasured**.
- **Language and accessibility:** The frontend includes localization and accessibility foundations. Full Hindi translation and a passed WCAG 2.2 AA audit are not implied.
- **Historical/forecast coverage:** Charts and planning depend on available data; a requested period does not guarantee the provider has usable observations for that period.

## 5. System architecture

AirWise uses a **modular monolith**: one FastAPI application with explicit domain services, repositories, and schemas, rather than independently deployed microservices for every feature. This keeps authorization, numerical calculations, and persistence boundaries visible while allowing background work to run separately.

```mermaid
flowchart TB
    Browser["Browser: public pages and authenticated workspace"]
    UI["Next.js App Router: React and TypeScript"]
    API["FastAPI: /api/v1, validation, sessions, CSRF, RBAC"]
    Domains["Domain services: AQI, weather, planning, impact, alerts, community"]
    AI["Copilot orchestration: tools, RAG, guardrails, Gemini gateway"]
    PG[("PostgreSQL: relational data, PostGIS, pgvector")]
    Redis[("Redis: cache, quotas, broker")]
    Workers["Celery worker and Beat scheduler"]
    Environment["Environmental providers"]
    Gemini["Google Gemini: generation and embeddings"]
    Email["Console or Resend email"]

    Browser --> UI
    UI <-->|"JSON and validated SSE"| API
    API --> Domains
    API --> AI
    Domains --> PG
    Domains --> Redis
    Domains --> Environment
    AI --> Domains
    AI --> PG
    AI --> Redis
    AI --> Gemini
    Redis <--> Workers
    Workers --> Domains
    Domains --> Email
```

### Technology choices

| Layer | Main technologies | Purpose |
| :--- | :--- | :--- |
| Frontend | Next.js 15, React 19, strict TypeScript | App Router pages, interactive workspace, typed API consumption. |
| UI and state | Tailwind CSS, Radix/shadcn-style primitives, TanStack Query, Zustand | Shared visual tokens, accessible controls, server/client state. |
| Forms and visualization | React Hook Form, Zod, Recharts, MapLibre GL | Input validation, pollutant trends, station maps. |
| Backend | Python 3.12+, FastAPI, Pydantic v2 | Validated APIs and domain orchestration. |
| Persistence | SQLAlchemy 2.x async, Alembic, PostgreSQL 16 | Ownership-scoped data access and versioned schema changes. |
| Spatial and retrieval | PostGIS, pgvector, PostgreSQL full-text search | Saved/station locations and hybrid evidence retrieval. |
| Background work | Redis 7, Celery worker, Celery Beat | Caching, AI quotas, scheduled ingestion, alerts and maintenance. |
| AI | Gemini REST gateway and embeddings | Narrative generation and semantic search; never authoritative numerical math. |
| Validation | Ruff, MyPy, Pytest, ESLint, TypeScript, Vitest, Playwright | Backend, frontend, integration and browser checks. |
| Operations | Docker Compose, GitHub Actions, Vercel entrypoint, Prometheus/OpenTelemetry hooks | Local services, release workflows and observability. |

Dependency manifests are authoritative: [backend dependencies](./backend/pyproject.toml) and [frontend dependencies](./frontend/package.json).

### Persistence domains

This is a conceptual data map, not an exhaustive entity-relationship diagram:

```mermaid
flowchart LR
    Identity["Identity: users, profiles, preferences, sessions, saved locations"]
    Telemetry["Environment: sources, stations, measurements, forecasts, weather"]
    Knowledge["Knowledge: documents, chunks, ingestion jobs"]
    Chat["Assistant: conversations, messages, generation metadata"]
    Planning["Planning: recommendations, feedback, routines, activities"]
    Impact["Impact: emission factors, user actions, estimates"]
    Alerts["Alerts: rules, notifications, deliveries"]
    Community["Community: groups, members, initiatives, participation"]
    Governance["Governance: audit logs and system settings"]

    Identity --> Chat
    Identity --> Planning
    Identity --> Impact
    Identity --> Alerts
    Identity --> Community
    Telemetry --> Planning
    Telemetry --> Alerts
    Knowledge --> Chat
    Planning --> Impact
    Governance -.-> Identity
    Governance -.-> Knowledge
    Governance -.-> Community
```

See the [system architecture](./docs/architecture.md), [database specification](./docs/database.md), and [architecture decisions](./docs/architecture-decisions/) for deeper design context.

## 6. Environmental data and AQI methodology

### Data flow and trust boundaries

```mermaid
flowchart TD
    Request["Request city and explicit AQI standard"] --> Cache{"Usable cached response?"}
    Cache -->|"Yes"| Response["Return conditions with provenance and freshness"]
    Cache -->|"No"| Provider["Fetch selected environmental provider"]
    Provider --> Available{"Provider available?"}
    Available -->|"No"| Fallback["Try configured fallback"]
    Available -->|"Yes"| Normalize["Normalize concentrations, units, timestamps, source type"]
    Fallback -->|"Usable data"| Normalize
    Fallback -->|"No usable data"| Missing["Explicit unavailable or qualified stale-data state"]
    Normalize --> Preconditions{"Required pollutants and averaging inputs valid?"}
    Preconditions -->|"Yes"| AQI["Calculate with the selected standard only"]
    Preconditions -->|"No"| NoAQI["AQI null; explain missing inputs"]
    AQI --> Store["Persist/cache applicable telemetry"]
    Store --> Response
    NoAQI --> Response
    Missing --> Response
```

Each result must make it possible to distinguish:

- **Observation vs forecast:** A forecast is modeled future information, not a measurement.
- **Station vs model:** A city/regional model output is not street-level sensor evidence.
- **Fresh vs stale:** Measurement time and freshness qualifications remain visible.
- **Real vs fixture:** Synthetic local/test readings carry `is_development_fixture: true`.
- **Available vs insufficient:** Missing pollutants or required averaging inputs must not be filled with guessed AQI values.

### AQI standards are deliberately isolated

| Standard | Identifier | Categories |
| :--- | :--- | :--- |
| US EPA | `us_epa` | Good; Moderate; Unhealthy for Sensitive Groups; Unhealthy; Very Unhealthy; Hazardous. |
| India National AQI | `india_naqi` | Good; Satisfactory; Moderate; Poor; Very Poor; Severe. |

The calculators use pollutant-specific breakpoint interpolation:

```text
Ip = ((Ihi - Ilo) / (Bhi - Blo)) * (Cp - Blo) + Ilo
AQI = maximum valid pollutant sub-index
```

Here `Cp` is the concentration after applicable standard-specific preprocessing; `Blo/Bhi` are concentration breakpoints and `Ilo/Ihi` are index breakpoints.

India NAQI requires at least three qualifying pollutants, including PM2.5 or PM10, with the applicable averaging periods. US EPA uses its own concentration truncation, units, and averaging rules. Neither standard should be calculated by simply relabeling a provider's unrelated index.

Tracked pollutants are **PM2.5, PM10, NO2, SO2, CO, and O3**. Units are explicit; gas conversions require valid conversion assumptions, not silent interchange of mass and volume concentrations.

Read the [environmental methodology](./docs/environmental-methodology.md) and [scientific safety guardrails](./docs/safety.md) for formulas, limits, and source context.

## 7. AirWise Copilot and trusted RAG

Copilot is not an unrestricted autonomous chatbot. It is a bounded backend pipeline that retrieves authorized context, invokes allowlisted services, and validates the answer before displaying generated narrative.

### Grounded answer pipeline

```mermaid
flowchart TD
    User["Question, city, standard, explicit AI consent"] --> Gate["Authenticate; validate input; enforce quotas"]
    Gate --> Safety{"Urgent medical or elevated environmental risk?"}
    Safety -->|"Requires conservative response"| Safe["Deterministic safety guidance"]
    Safety -->|"Normal grounded request"| Context["Build minimized authorized context"]
    Context --> Tools["Bounded allowlisted tools: maximum four selected calls"]
    Tools --> Evidence["Retrieve reviewed evidence: vector and lexical search"]
    Evidence --> Rules["Attach verified conditions, calculator results, safety constraints"]
    Rules --> Model["Gemini generates structured narrative"]
    Model --> Verify{"Schema, citations, numbers, safety valid?"}
    Verify -->|"Yes"| Stream["Emit validated deltas and citations; persist if enabled"]
    Verify -->|"No"| Retry["At most one corrective generation retry"]
    Retry --> Recheck{"Valid after retry?"}
    Recheck -->|"Yes"| Stream
    Recheck -->|"No"| Safe
    Tools -->|"Unavailable required data or service"| Safe
    Evidence -->|"Insufficient evidence"| Safe
```

The full design is described as a [14-stage orchestration pipeline](./docs/ai-architecture.md#1-end-to-end-orchestration-pipeline). It includes input checks, context building, tool execution, RAG, generation, verification, bounded retry, and explicit fallback.

### Twelve tools, not arbitrary execution

| Tool | Backing purpose |
| :--- | :--- |
| `get_current_air_quality` | Current pollutant/AQI conditions with provenance. |
| `get_air_quality_forecast` | Available forecast slices and confidence. |
| `get_historical_air_quality` | Available historical trends. |
| `get_weather_conditions` | Weather and dispersion context. |
| `get_user_preferences` | Active user's preferences, with separate sharing consent. |
| `get_saved_locations` | Active user's coarse saved-location metadata. |
| `retrieve_environmental_guidelines` | Reviewed evidence and real document identifiers. |
| `calculate_transport_emissions` | Deterministic transport CO2e comparison. |
| `estimate_exposure_change` | Deterministic relative exposure estimate. |
| `compare_daily_routines` | Read-only comparison of the active user's routine options. |
| `generate_sustainable_alternatives` | Exposure-screened alternatives. |
| `get_community_initiatives` | Authorized/public initiative summaries. |

Tool scope does not grant guest access to the authenticated chat endpoint. Private tools enforce the active user's ownership outside the model prompt; model output cannot choose another account, run SQL, fetch arbitrary URLs, or automatically save plans.

### How evidence and output remain trustworthy

- **Corpus:** Operator-reviewed local manifests contain short original editorial summaries of WHO, EPA, and NCDC guidance. Ingestion does not download arbitrary user-supplied URLs.
- **Indexing:** Content hashes, source metadata and review dates are stored with chunks. Gemini embeddings use `gemini-embedding-001` with 768 dimensions by default.
- **Retrieval:** PostgreSQL combines vector similarity and full-text ranking using reciprocal-rank fusion. Model-version compatibility and source qualifications matter.
- **Citations:** References must belong to the current turn's retrieved documents. Citation metadata comes from stored records, not invented model prose.
- **Numbers:** Environmental readings and impact fields are assembled from backend results. Unsupported numerical claims in generated prose are rejected.
- **Streaming:** Status events show real progress, but raw unverified model tokens are **not** streamed. Answer deltas follow verification; persistence completes before the terminal completion event.
- **Fallback:** Missing credentials, unavailable evidence/services, exhausted quotas, or invalid output produce explicitly labeled deterministic guidance, not a simulated Gemini answer.
- **History:** `save_chat_history` controls persistence and reuse of prior turns. Turning it off does not erase existing history; deletion is a separate user action.

Actionable answers organize the situation, verified conditions, recommended action, rationale, estimated impact, uncertainty, safer alternatives, and evidence references.

## 8. Deterministic impact estimates

The LLM explains results; it does not own the calculations. The [backend calculators](./backend/app/services/impact/calculators.py) produce baseline/alternative values, a difference, units, methodology, assumptions, source references, confidence, calculation time, and `is_estimate: true`.

| Calculator | Core relationship | Interpretation and limits |
| :--- | :--- | :--- |
| Transport | `CO2e = distance_km * vehicle_km_factor / occupancy` | Comparison depends on the selected factor and occupancy; do not divide an already passenger-km factor twice. |
| Household electricity | `energy_kWh = power_kW * hours`; `CO2e = energy_kWh * grid_factor` | Factor- and usage-based estimate, not a utility-meter measurement. |
| Indoor filtration | `room_volume = area * height`; `clean_air_ACH = CADR / room_volume` | Clean-air delivery sizing with stated infiltration/source assumptions, not proof of indoor PM2.5 or clinical benefit. |
| Relative exposure | `index = outdoor_PM2.5 * duration * environment_modifier` | A time-weighted comparative index, not exact inhaled dose. |

For emissions and exposure comparisons, a positive `baseline - alternative` difference indicates a lower estimated value for the alternative. Filtration reports added clean-air changes instead; always interpret the metric and unit rather than treating every difference as carbon savings.

Reference factors and starter community records can be seeded with `python -m scripts.seed_reference_data`. Seeding does not establish live AQI coverage or independently verify every action a user logs.

**Indoor guidance boundaries:** Source control and appropriately sized filtration are relevant; houseplants are not a meaningful particulate-removal substitute, ozone-generating air cleaners are not recommended, and outdoor measurements do not establish indoor air quality.

## 9. Security, privacy, and user control

- **Sessions:** Argon2id password hashing, HTTP-only session cookies, session revocation, and CSRF checks on protected state-changing requests.
- **Authorization:** Backend role checks and ownership-scoped access for private records. Hiding an admin page is not the authorization boundary.
- **Secrets:** Provider keys belong on the backend. Never put secrets in `NEXT_PUBLIC_*`, browser storage, or committed environment files.
- **Location:** Explicit geolocation consent, precision metadata, and city selection as a non-geolocation path. Assistant context uses minimized location information.
- **AI consent:** Sending a question to Gemini requires explicit consent. Sharing household preferences is a separate opt-in; avoid identifying, clinical, or confidential content.
- **Account control:** Export, deletion, history controls, and session management are part of the API and settings experience.
- **Community:** Coarse boundaries and aggregate participation must not expose exact household coordinates or non-consented personal information.
- **Changes require authorization:** Tools do not silently modify preferences, accept routines, or enroll users in initiatives.

Implementation controls are not a legal certification. See the [privacy specification](./docs/privacy.md), [safety guide](./docs/safety.md), and [development agent rules](./AGENTS.md).

## 10. Repository structure

```text
AirWise/
|-- frontend/
|   |-- src/app/                  Next.js public, auth, dashboard, admin pages
|   |-- src/components/           Shared UI and visualizations
|   |-- src/features/             Feature-specific client experiences
|   |-- src/lib/                  API/SSE clients and shared utilities
|   |-- tests/                    Vitest unit and UI tests
|   `-- e2e/                      Playwright browser scenarios
|-- backend/
|   |-- app/api/v1/               Versioned FastAPI endpoints
|   |-- app/ai/                   Gateway, tools, RAG, prompts, guardrails
|   |-- app/services/             Domain rules and deterministic calculations
|   |-- app/repositories/         Persistence access
|   |-- app/models/               SQLAlchemy models
|   |-- app/schemas/              Pydantic request/response contracts
|   |-- app/integrations/         External-provider adapters
|   |-- app/workers/              Celery ingestion, alerts, maintenance
|   |-- alembic/                  Database migrations
|   |-- scripts/                  Reference seeding and reviewed knowledge ingestion
|   `-- tests/                    Unit, integration, contract, security, AI evaluations
|-- api/index.py                  Vercel entrypoint for the FastAPI application
|-- docs/                         Product, architecture, science, API, operations
|-- infrastructure/               Database initialization and monitoring configuration
|-- .github/workflows/            CI and manually dispatched deployment workflow
|-- .agents/skills/               Contributor guidance by domain
|-- docker-compose.yml            Local six-service topology
|-- docker-compose.test.yml       Test service configuration
|-- vercel.json                   Hosting rewrites and daily maintenance cron
`-- Makefile                      Convenience commands for compatible shells
```

## 11. Local setup

### Prerequisites

- Git.
- **Python 3.12+**; CI currently uses Python 3.12.
- **Node.js 22 recommended**, matching CI, and npm.
- Docker Desktop/Engine with Compose v2 for container execution.
- For full-service development: PostgreSQL 16 with **PostGIS and pgvector**, and Redis 7.

Commands below use **Windows PowerShell**, starting at the repository root unless a different working directory is stated. On macOS/Linux, use the equivalent shell paths and virtual-environment activation.

### A. Lightweight local demo: SQLite and labeled fixtures

This follows the repository's CI demo approach. It avoids a local PostgreSQL/Redis requirement and is useful for UI and deterministic-flow development. **It does not validate PostGIS, vector retrieval, live Gemini, production provider data, or scheduled delivery.**

Initialize environment files once; do not overwrite an existing customized file:

```powershell
Copy-Item .\backend\.env.example .\backend\.env
Copy-Item .\frontend\.env.example .\frontend\.env.local
```

In the backend terminal:

```powershell
Set-Location .\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"

# Process-local demo settings override backend\.env.
$env:APP_ENV = "development"
$env:DATABASE_URL = "sqlite+aiosqlite:///./airwise_local.sqlite3"
$env:REDIS_URL = ""
$env:AIR_QUALITY_PROVIDER = "fixture"
$env:WEATHER_PROVIDER = "fixture"

alembic upgrade head
python -m scripts.seed_reference_data
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Keep that terminal open. In a second terminal at the repository root:

```powershell
Set-Location .\frontend
npm install
npm run dev
```

The backend environment overrides apply only to that PowerShell process. Repeat them when restarting the backend, or put the selected development values in your untracked backend environment file.

### B. Native development with PostgreSQL and Redis

Use the same environment-file initialization and dependency installation as above, but configure the backend environment file for reachable services:

```dotenv
APP_ENV=development
DATABASE_URL=postgresql+asyncpg://airwise:airwise_dev_only@localhost:5432/airwise
REDIS_URL=redis://localhost:6379/0
AIR_QUALITY_PROVIDER=fixture
WEATHER_PROVIDER=fixture
```

The credentials above are local placeholders only. Ensure PostgreSQL has `postgis`, `vector`, `citext`, and `uuid-ossp` available/enabled, then run from the backend directory with its virtual environment active:

```powershell
alembic upgrade head
python -m scripts.seed_reference_data
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Remove any SQLite demo process overrides before using this mode; process environment values take precedence over the environment file.

For background ingestion, alerts, and maintenance, run a Celery worker and one Beat scheduler in separate terminals/environments. The Compose/Linux execution path is preferred for workers:

```text
celery -A app.workers.celery_app:celery_app worker --loglevel=info
celery -A app.workers.celery_app:celery_app beat --loglevel=info
```

The included Beat schedule polls priority-city AQI and evaluates alerts every 15 minutes, and cleans expired sessions daily at 02:30 UTC.

### C. Docker Compose: full service topology with required preparation

**The checked-in Compose stack is not a guaranteed one-command complete setup.** Two details require attention:

1. Backend/worker/scheduler currently read the backend **example** environment file, not your customized backend environment file. Frontend reads its example file too.
2. The default `postgis/postgis:16-3.4` image must not be assumed to contain pgvector. Initialization enables `vector` only if available, while the assistant migration requires it.

Before starting, provide a PostgreSQL image with both PostGIS and pgvector available. If using a local `docker-compose.override.yml`, the following illustrates the necessary overrides. **Replace the image placeholder with an image you have built or verified.** This snippet is documentation, not an additional checked-in configuration:

```yaml
services:
  postgres:
    image: your-verified-postgres16-postgis-pgvector-image
  backend:
    env_file:
      - ./backend/.env
  worker:
    env_file:
      - ./backend/.env
  scheduler:
    env_file:
      - ./backend/.env
  frontend:
    env_file:
      - ./frontend/.env.local
```

Compose's existing container-specific `DATABASE_URL` and `REDIS_URL` overrides should remain in effect. The default PostgreSQL and Redis services are **not published to host ports**, so a native host backend cannot reach them at `localhost` without an explicit port override.

Once the image and effective configuration are ready:

```powershell
docker compose config
docker compose up --build -d postgres redis backend
docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.seed_reference_data
docker compose up --build -d frontend worker scheduler
docker compose ps
```

Provider-backed worker tasks also need outbound connectivity. The base worker/scheduler services use an internal-only network; configure appropriate egress when enabling external integrations.

PostgreSQL initialization scripts run only on a new database volume. Changing an image or initialization script does not retroactively install an extension in existing data.

### Verify the application

| Endpoint | Expected use |
| :--- | :--- |
| `http://localhost:3000` | Frontend. |
| `http://localhost:8000/docs` | Interactive OpenAPI documentation in non-production mode. |
| `http://localhost:8000/health/live` | Application liveness, with `status: "ok"`. |
| `http://localhost:8000/health/ready` | Database readiness, with `status: "ready"` and `checks.database: "ok"` when reachable. |

```powershell
Invoke-RestMethod "http://localhost:8000/health/live"
Invoke-RestMethod "http://localhost:8000/health/ready"
Invoke-RestMethod "http://localhost:8000/api/v1/air-quality/current?city=Delhi&standard=india_naqi"
```

Open `/air-quality`, choose a city/standard, and confirm the development fixture label is visible in fixture mode. Register an account before exploring private dashboard flows.

**Readiness is not an all-integrations test:** It checks database access and reports configured provider modes; it does not prove Redis, Gemini, corpus retrieval, or notification delivery works. Inspect the response body, not just HTTP success.

## 12. Configuration and live integrations

Use the [backend environment template](./backend/.env.example) and [frontend environment template](./frontend/.env.example) as starting points. The [settings model](./backend/app/core/config.py) defines accepted values and startup checks.

| Setting | Purpose / important constraint |
| :--- | :--- |
| `APP_ENV`, `DEBUG` | Environment and debugging. Production rejects debug mode and environmental fixture providers. |
| `DATABASE_URL`, `REDIS_URL` | Persistence, caching, budgets and background broker. SQLite/empty Redis is a limited demo configuration. |
| `AUTH_SECRET_KEY`, `AUTH_COOKIE_SECURE` | Replace development secrets; use secure cookies for production HTTPS. |
| `FRONTEND_URL`, `BACKEND_URL` | Public origins for CORS/auth links and backend URLs; keep hostname choices consistent. |
| `AIR_QUALITY_PROVIDER` | `openaq`, `openweather`, `cpcb` interface, or explicit `fixture`. |
| `AIR_QUALITY_FALLBACK_PROVIDER` | `openaq`, `openweather`, or `none`. |
| `AIR_QUALITY_API_KEY` | Current AQI adapter credential. Primary/fallback share this setting; do not assume one provider's key works for another. |
| `WEATHER_PROVIDER`, `WEATHER_API_KEY` | `openweather`, `open_meteo`, or `fixture`; credential requirements vary. |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Backend-only Gemini generation; default model is `gemini-2.5-flash`. |
| `EMBEDDING_MODEL` | Default `gemini-embedding-001`; model changes require compatible re-ingestion. |
| `AI_REQUESTS_PER_MINUTE` | Per-user AI rate limit; template default is 10. |
| `AI_DAILY_TOKEN_BUDGET`, `AI_MAX_OUTPUT_TOKENS` | Usage bounds; template defaults are 200000 and 2048. Reservations are conservative, not a billing report. |
| `EMAIL_PROVIDER`, `EMAIL_API_KEY`, `EMAIL_FROM_ADDRESS` | Local console transport or Resend delivery. Console mode does not send real email. |
| `NEXT_PUBLIC_API_BASE_URL` | Browser API base: local template uses `http://localhost:8000/api/v1`; Vercel uses `/api/v1`. Not a secret. |
| `NEXT_PUBLIC_DEFAULT_AQI_STANDARD` | Default UI standard, currently `india_naqi`. |
| `DATABASE_SERVERLESS_POOL` | Enables serverless-friendly SQLAlchemy connection behavior. |
| `CRON_SECRET`, `METRICS_INTERNAL_TOKEN` | Protect maintenance endpoints and metrics access. |

### Enable real Copilot responses

1. Use the full-service PostgreSQL/Redis configuration and migrate the database.
2. Set backend-only `GEMINI_API_KEY`; restart the backend after changing settings.
3. From the backend directory, ingest the reviewed corpus:

   ```powershell
   python -m scripts.ingest_knowledge
   ```

4. Sign in, open `/dashboard/assistant`, select a city and AQI standard, and explicitly consent to Gemini processing.
5. Verify retrieval, a non-fallback answer, real stored citations, and expected quota/history behavior.

The [knowledge manifest](./backend/scripts/knowledge_sources.json) is reviewed input, not a user-upload endpoint. PostgreSQL vector retrieval and Redis quotas must be checked against real configured services. SQLite's lexical test path is not proof of hybrid retrieval.

### Enable real environmental readings

Select a supported live provider, configure its credential where needed, and verify pollutant units, timestamps, station/model source type, history/forecast coverage, and unavailable-data behavior. Live provider selection does not guarantee sufficient averaging inputs to calculate either AQI standard.

Keep fixture mode explicit for development. It is rejected for both air quality and weather when `APP_ENV=production`.

## 13. API overview

All business APIs are under `/api/v1`. Standard JSON success responses use `data` and `meta`; domain/validation failures use `error.code`, `error.message`, and `error.request_id`. Health endpoints and SSE streams have their own shapes.

| API family | Representative operations |
| :--- | :--- |
| `/auth` | Registration/login, logout/refresh, email verification/reset, current principal, session management. |
| `/users` | Current-user data/preferences, `GET /users/me/export`, `DELETE /users/me`. |
| `/locations` | Search and ownership-scoped saved-location CRUD. |
| `/air-quality` | `GET /current`, `/history`, `/forecast`, `/stations`, `/map`. |
| `/weather` | `GET /current`. |
| `/assistant` | Capabilities, chat, `POST /chat/stream`, conversation history/deletion. |
| `/recommendations`, `/routines` | Generate/read recommendations, feedback, generate/edit/save routines. |
| `/impact` | Reference factors, `POST /calculate`, action logging, summary/history. |
| `/alerts`, `/notifications` | Rule management/evaluation and notification operations. |
| `/communities` | Groups, initiatives, participation, reports and summaries. |
| `/admin` | Role-protected administration, governance, settings and audit data. |
| `/system/cron` | Bearer-secret-protected maintenance, ingestion and alert evaluation. |

Example public request:

```http
GET /api/v1/air-quality/current?city=Delhi&standard=india_naqi
```

Historical periods are `24h`, `7d`, and `30d`. Forecast requests accept a bounded `hours` value. Exact required fields and authorization requirements are defined by the running OpenAPI schema and [API documentation](./docs/api.md); the table above is a navigation guide, not a complete contract.

For protected mutations, use the authenticated cookies and repository-standard `X-CSRF-Token` handling. Do not bypass CSRF to make an API example work.

## 14. Testing and quality gates

Run checks from the relevant project directory after installing its dependencies:

**Backend** - virtual environment active:

```powershell
Set-Location .\backend
python -m ruff check app scripts tests
python -m mypy app
python -m pytest
```

**Frontend** - separate terminal at repository root:

```powershell
Set-Location .\frontend
npm run lint
npm run typecheck
npm run test
npm run build
```

**Browser tests** - with backend and frontend already running:

```powershell
# From frontend; install the browser once.
npx playwright install chromium
npx playwright test --project=chromium
```

Set `PLAYWRIGHT_BASE_URL` if the frontend is not at `http://localhost:3000`. Playwright does not start the application servers through its current configuration.

### What validation covers and what it does not

| Suite | Main purpose |
| :--- | :--- |
| Backend unit tests | AQI boundaries, deterministic math, gateway and domain rules. |
| Integration/contract/security tests | API flows, persistence behavior, authorization and error contracts. |
| AI evaluations | Safety, grounding, citation/number validation and fallback scenarios. |
| Vitest | UI behavior, AQI standards, assistant streaming and feature workflows. |
| Playwright | Browser flows including the full-stack user journey and assistant UI scenario. |
| CI | Backend checks, frontend checks/build, browser journey, and Docker image builds. |

The [CI workflow](./.github/workflows/ci.yml) uses SQLite and labeled fixtures for its full-stack journey. Assistant browser scenarios mock API output, and automated Gemini tests use mocks. These tests **do not certify live credentials, PostgreSQL vector ranking, production provider coverage, Redis connectivity, or an operational deployment**.

Targets such as WCAG 2.2 AA, cached-AQI p95 below 300 ms, standard API p95 below 500 ms, and first SSE event below 3 seconds are **engineering goals**, not measured achievements asserted by this README.

## 15. Deployment and operations

### Supported deployment shapes

| Shape | Appropriate use | Operational responsibility |
| :--- | :--- | :--- |
| Native/Compose services | Development or an operated long-running stack. | Database extensions, service networking, worker/Beat availability, backups and secrets. |
| Vercel frontend + Python entrypoint + managed services | Serverless application hosting. | Compatible managed PostgreSQL/Redis, function limits, cron frequency, provider quotas and production validation. |

```mermaid
flowchart TB
    Users["Users over HTTPS"] --> Vercel["Vercel routing"]
    Vercel --> Next["Next.js frontend"]
    Vercel -->|"Same-origin /api/v1 and health rewrites"| Python["Python function: api/index.py mounts FastAPI"]
    Cron["Configured daily cron: 02:30 UTC"] -->|"Bearer CRON_SECRET"| Python
    Python --> PG[("Managed PostgreSQL: PostGIS and pgvector")]
    Python --> Redis[("Managed Redis")]
    Python --> Providers["AQI, weather, Gemini, email providers"]
    Scheduler["Additional operated scheduling if required"] -.->|"Authenticated ingestion and alert endpoints"| Python
```

The [Vercel configuration](./vercel.json) rewrites API, health and metrics requests to the [Python entrypoint](./api/index.py). Same-origin `/api/v1` requests avoid a separate third-party-cookie hosting arrangement. Local Next.js also has an API rewrite, while the example frontend configuration uses the backend's absolute local URL.

### Serverless limitations to plan for

- **No guaranteed $0/month:** Free-tier hosting may be suitable for limited usage, but eligibility, quotas, paid provider APIs, LLM usage, backups and traffic can incur costs. Check the terms and limits of each chosen service; this README does not promise free production operation.
- **No always-on Celery on Vercel functions:** Operate workers elsewhere or use appropriately authenticated scheduling. A serverless function is not a replacement for an always-running worker.
- **Only daily maintenance is configured in the manifest:** It cleans sessions and refreshes telemetry. The additional ingestion and alert-evaluation endpoints exist, but no recurring alert-evaluation cron is included in the current manifest.
- **Function duration:** The manifest requests a 60-second maximum. Verify plan/runtime support and workload duration, especially multi-city ingestion and AI orchestration.
- **Database:** Use a compatible PostgreSQL endpoint with the required extensions and serverless connection settings; a managed provider name alone does not prove extension availability.
- **Monitoring:** Exported metrics use an in-process registry. Treat them appropriately for ephemeral/multiple instances, not as durable global counters.

### Production preparation

1. Configure `APP_ENV=production`, `DEBUG=false`, `AUTH_COOKIE_SECURE=true`, a strong replacement `AUTH_SECRET_KEY`, and non-fixture environmental providers.
2. Set production origins, `NEXT_PUBLIC_API_BASE_URL=/api/v1`, compatible database/Redis URLs, and `DATABASE_SERVERLESS_POOL=true` where appropriate.
3. Configure backend provider credentials, email delivery, `CRON_SECRET`, and `METRICS_INTERNAL_TOKEN`; keep secrets out of the frontend and repository.
4. Run migrations, seed reference records, and ingest reviewed knowledge against the intended database.
5. Verify live providers, quotas, retrieval/citations, cookie/CSRF flows, history/export/deletion, and the required alert schedule.
6. Verify application health, accessibility, latency, security, backup/restore and rollback procedures before release.

The [deployment workflow](./.github/workflows/deploy.yml) is manually dispatched, accepts a git ref and optional migrations, and targets the GitHub `production` environment. Configure required environment reviewers to enforce approval. It does not itself prove the selected ref has passed every release gate.

### Observability and recovery

- `/health/live` checks liveness; `/health/ready` checks database readiness.
- `/metrics` exposes HTTP, AQI cache and LLM request/fallback metrics; configure the scrape token and use `X-Metrics-Token`.
- OpenTelemetry instrumentation is conditional on `OTEL_EXPORTER_OTLP_ENDPOINT`.
- Database backups, restore drills and migration rollback must be verified on the selected provider; do not assume free plans include every recovery feature.
- `docker compose down` stops the local stack without removing named volumes. **Do not use `docker compose down -v` or `make clean` unless you intend to delete local database/cache data.**

See the [deployment guide](./docs/deployment.md) and [infrastructure deployment notes](./infrastructure/deployment/README.md) for operational context. Any older zero-cost wording in design documents is a deployment aspiration, not a guarantee.

## 16. Troubleshooting

| Symptom | Check / corrective action |
| :--- | :--- |
| Database readiness is degraded | Inspect `DATABASE_URL`, database availability and credentials. For Compose, remember databases have no host-published ports by default. |
| Migration says extension `vector` is unavailable | Supply PostgreSQL with pgvector installed, alongside PostGIS; rerun migrations after correcting extension availability. The default Compose image is not proof of pgvector support. |
| Backend changes to the environment file have no effect | Restart the backend, inspect process environment overrides, and check Compose's effective `env_file` configuration. |
| UI shows development fixture data | Expected in fixture mode. Configure and verify a live provider to obtain real readings; never simply remove the label. |
| AQI or forecast is unavailable | Check provider credentials, city coverage, pollutant units, averaging inputs and timestamps. Missing data is not a reason to invent values. |
| Gemini returns safety fallback | Check the key, Redis budget/rate-limit service, ingested compatible corpus, provider availability and validation/fallback reason. |
| Google login does not complete | The token exchange remains a stub; use email/password until the integration is completed. |
| Real email never arrives | `EMAIL_PROVIDER=console` is local logging only. Configure Resend and verify sending-domain/provider requirements. |
| Alerts do not run automatically | Confirm a worker plus Beat, or a separately configured authenticated cron, evaluates rules. Vercel's included daily maintenance does not evaluate alerts. |
| Web push is not delivered | The channel is currently unconfigured, not a complete push implementation. |
| Login/CSRF requests fail | Keep frontend/backend origins and `localhost` vs `127.0.0.1` usage consistent; check cookies and CSRF headers. |
| Playwright cannot connect | Start both application servers first and check `PLAYWRIGHT_BASE_URL`; the test config does not launch them. |
| PowerShell blocks virtual-environment activation | Invoke `.\.venv\Scripts\python.exe` and the corresponding installed executables directly; changing machine-wide execution policy is unnecessary. |

For container diagnosis, use `docker compose ps` and `docker compose logs backend worker scheduler`. Avoid publishing logs containing credentials or personal data.

## 17. Roadmap and documentation

The product is organized into seven delivery phases:

1. Architecture and foundation.
2. Authentication, preferences and locations.
3. Environmental data and isolated AQI standards.
4. Copilot and trusted RAG.
5. Recommendations, routines and deterministic impact.
6. Alerts and community.
7. Hardening, E2E validation and deployment.

Code exists across these areas, while some integrations remain explicitly incomplete. Phase titles are an implementation structure, not a substitute for verified acceptance criteria. See the [master plan](./docs/planning.md) for dependencies and completion gates.

| Document | What it explains |
| :--- | :--- |
| [Product requirements](./docs/prd.md) | Problem, personas, target experiences and product requirements. |
| [Implementation plan](./docs/planning.md) | Seven phases, dependencies, risks and Definition of Done. |
| [System architecture](./docs/architecture.md) | Application boundaries and component responsibilities. |
| [Architecture decisions](./docs/architecture-decisions/) | Rationale for the monolith, storage, auth, AQI isolation and hosting. |
| [API contract](./docs/api.md) | Endpoint and payload design; compare with runtime OpenAPI. |
| [Database specification](./docs/database.md) | Persistence entities and schema design. |
| [AI architecture](./docs/ai-architecture.md) | Orchestration, tools, RAG, generation and verification. |
| [Safety](./docs/safety.md) | Scientific/medical boundaries and exposure-first safeguards. |
| [Environmental methodology](./docs/environmental-methodology.md) | AQI, impact formulas and assumptions. |
| [Privacy](./docs/privacy.md) | Consent, minimization, retention and account governance. |
| [Development guide](./docs/development.md) | Contributor setup and focused validation commands. |
| [Deployment guide](./docs/deployment.md) | Hosting configuration and operational runbooks. |

Specifications include target behavior as well as implementation guidance. When a specification describes a future integration, do not treat it as evidence that the corresponding adapter or deployment is already operational.

## 18. Contributing and license

Before changing domain logic, read [AGENTS.md](./AGENTS.md) and the relevant [agent skill](./.agents/skills/). Keep changes scoped, update directly related documentation, and run the checks that cover the behavior being changed.

Especially important:

- Never fabricate environmental readings, citations, or impact measurements.
- Keep AQI standards separate and missing/stale data explicit.
- Preserve exposure-first decisions, backend-owned numerical math, account ownership, and user consent.
- Do not claim a feature is complete while relevant tests or acceptance gates fail.
- Do not commit credentials, local databases, generated artifacts, or personal data.

**License:** MIT; see [LICENSE](./LICENSE). External datasets, provider APIs, maps and cited source material retain their own licenses and usage terms.
