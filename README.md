# AirWise AI

> **Breathe Smarter. Live Cleaner. Act Together.**

**AirWise AI is an environmental wellness platform that turns air-quality information into practical, exposure-first daily decisions.** It combines environmental-provider data, deterministic safety rules and impact calculators, a grounded conversational assistant, daily planning, alerts, and neighborhood action.

The goal is not merely to answer **"What is the AQI?"** It is to help answer **"What can I safely do today, why does it help, and what are the limits of that advice?"**

**Project status:** The repository contains frontend pages, backend APIs, migrations, workers, and automated tests across the product modules below. This is a production-oriented implementation, **not a claim of production certification**. Live integrations, deployment limits, accessibility, performance, and the [15-point Definition of Done](./docs/planning.md#5-15-point-definition-of-done-mandatory-gate) must be validated for the intended environment.

**Safety notice:** AirWise provides environmental guidance, not medical diagnosis, treatment, or guaranteed health outcomes. Synthetic development data is explicitly labeled. Missing data remains unavailable; estimates are not measurements.

---

## Contents

- [1. Chosen vertical and problem statement](#1-chosen-vertical-and-problem-statement)
- [2. Approach and logic](#2-approach-and-logic)
- [3. How the solution works](#3-how-the-solution-works)
- [4. Assumptions made and implementation boundaries](#4-assumptions-made-and-implementation-boundaries)
- [5. Evaluation focus areas](#5-evaluation-focus-areas)
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

## 1. Chosen vertical and problem statement

### Chosen vertical

**Vertical:** **Environmental Wellness, Climate Resilience, and Public-Safe Urban Air Pollution Decision Support** *(GenAI + Deterministic Sustainability & Health-Protective Lifestyle Intelligence)*.

AirWise AI targets one of the highest-impact daily environmental challenges affecting urban residents: **chronic ambient air pollution and severe seasonal winter smog**. Across high-density cities, millions of parents, commuters, older adults, caregivers, students, and neighborhood organizers face hazardous particulate spikes (`PM2.5`, `PM10`) and gaseous pollutants (`NO2`, `SO2`, `CO`, `O3`), yet existing consumer tools stop at displaying raw AQI numbers or ungrounded generic tips.

### Problem statement

A raw pollution index does not tell a parent how to time school runs or indoor play, a commuter how to weigh roadside inhalation exposure against tailpipe carbon savings, or a caregiver how to protect vulnerable family members when data is stale or incomplete.

| Gap | Why it matters |
| :--- | :--- |
| **Numbers without actionable context** | AQI categories do not directly explain which routines to change, which alternatives are feasible, or when guidance is uncertain. |
| **Fragmented information** | Air quality, weather dispersion, indoor filtration sizing, commute comparisons, and community initiatives live in disconnected tools. |
| **Incompatible AQI standards** | US EPA AQI (`us_epa`) and India National AQI (`india_naqi`) use different breakpoints, averaging rules, and category names. Treating them as interchangeable misleads users. |
| **Incomplete or stale observations** | A missing pollutant, delayed station reading, or regional atmospheric model output must never masquerade as a fresh street-level sensor measurement. |
| **Conflicting safety and sustainability goals** | A low-carbon commute is not automatically a low-exposure commute. Outdoor walking or cycling is unsafe to recommend during severe smog solely to save `CO2e`. |
| **Unreliable AI explanations** | An unconstrained chatbot can hallucinate local PM2.5 readings, invent emission math, or fabricate scientific citations. |
| **Privacy and control concerns** | Helpful personalization must not force GPS tracking, leak household data across accounts, or mutate user schedules without explicit confirmation. |

**Core problem statement:** People need a trustworthy, accessible system that translates verified environmental telemetry into safer, realistic daily actions while keeping observations, forecasts, deterministic estimates, and general public-health guidance strictly distinct.

---

## 2. Approach and logic

AirWise AI uses a **Hybrid Deterministic + Grounded GenAI Architecture**. Pure rule tables cannot answer nuanced household questions in plain language, while pure LLMs cannot be trusted to compute AQI sub-indices, calculate `CO2e` or `CADR/ACH`, or enforce safety boundaries reliably. AirWise separates those responsibilities cleanly:

1. **Deterministic Backend Owns All Math & Safety Gates:**
   - Standard-isolated Python calculators ([`aqi_calculator.py`](./backend/app/services/air_quality/aqi_calculator.py)) compute `india_naqi` and `us_epa` sub-indices from normalized pollutant concentrations—returning `unavailable` (`aqi: null`) whenever required pollutants or averaging windows are missing.
   - Deterministic environmental calculators ([`calculators.py`](./backend/app/services/impact/calculators.py)) compute passenger-kilometer transport `CO2e`, household electricity `kWh`/`CO2e`, indoor HEPA `CADR`/`ACH` sizing, and time-weighted relative exposure indices—always tagged `is_estimate: true` with explicit assumptions and source references.
   - Deterministic safety rules ([`safety_engine.py`](./backend/app/services/recommendations/safety_engine.py) and [`safety_rules.py`](./backend/app/ai/guardrails/safety_rules.py)) block unsafe outdoor exercise or active-travel suggestions during poor/severe pollution before any AI narrative is generated.
2. **Strict Six-Tier Decision Priority Hierarchy:**
   Every recommendation, routine slot, and commute screening follows an explicit, invariant priority order:
   `1. Immediate Exposure Safety -> 2. User Schedule Constraints -> 3. Practical Feasibility -> 4. Emission Reduction -> 5. Cost -> 6. Convenience`.
3. **Separation of Three Distinct Impact Dimensions:**

| Dimension | What AirWise evaluates | What it strictly refuses to claim |
| :--- | :--- | :--- |
| **1. Personal exposure reduction** | Lowering time or estimated concentration in polluted microenvironments; choosing cleaner windows, enclosed transit, and indoor HEPA filtration. | Exact biological inhaled dose, clinical diagnosis/outcomes, or a measured indoor reading inferred from outdoor AQI. |
| **2. Emission reduction** | Estimated transport (`passenger-km`) and household electricity (`kWh`) `CO2e` differences using published emission factors and occupancy assumptions. | That a lower-emission option (e.g., cycling in severe smog) is safe to take today. |
| **3. Community impact** | Voluntary neighborhood clean-air challenges, moderated tips, and privacy-preserving aggregate action counts. | That an individual household pledge or neighborhood challenge measurably lowers city-wide ambient AQI. |

4. **Bounded, Verifiable GenAI & Hybrid RAG:**
   - **AirWise Copilot** runs a 14-stage backend pipeline with urgent medical red-flag screening, prompt-injection delimiters, a strict **12-tool RBAC-gated allowlist** (maximum 4 calls per turn), PostgreSQL hybrid vector + lexical evidence retrieval (`pgvector` + full-text reciprocal-rank fusion), Pydantic v2 structured output enforcement, post-LLM citation ID & numerical verification, at most one corrective retry, and a deterministic safe fallback when credentials, quotas, or validations fail.
   - Raw unverified LLM tokens are **never** streamed to the browser; SSE `delta` chunks are emitted only after schema, citation, and numerical verification succeed.
5. **Consent-First Privacy & Defense-in-Depth Security:**
   - Guests can inspect city AQI without registering or granting geolocation. Authenticated users control exact vs. coarse location precision, per-request Gemini consent, preference sharing, chat retention, session revocation, portable JSON export, and full account erasure.

---

## 3. How the solution works

### End-to-end user workflow and personas

| Persona | Core decision need | Key AirWise modules |
| :--- | :--- | :--- |
| **Parents & families** | Plan school runs and outdoor play; size bedroom HEPA filtration safely. | Dashboard, Routine Planner, Indoor Air, Smart Alerts |
| **Daily commuters** | Compare solo car, metro, carpool, EV, and active modes across exposure *and* `CO2e`. | Transport & Impact Engine, Routine Planner, Copilot |
| **Older adults & caregivers** | High-contrast text-labeled AQI badges, calm conservative precautions, quiet-hour alerts. | Public/Auth Air Quality Explorer, Smart Alerts, Copilot |
| **Students & learners** | Understand `PM2.5` vs `PM10`, inspect transparent formulas, read cited WHO/EPA/CPCB guidance. | Learn Hub, Copilot Citations, Impact Tracker |
| **Community organizers** | Coordinate neighborhood no-idling or anti-waste-burning drives with privacy-safe aggregates. | Community Hub, Moderation Queue |

```mermaid
flowchart LR
    Discover["1. Explore public AQI & Learn Hub"] --> City["2. Select city & isolated AQI standard"]
    City --> Conditions["3. Inspect pollutants, provenance & freshness"]
    Conditions --> Account["4. Register & set optional household preferences"]
    Account --> Guidance["5. Ask Copilot or generate 5-domain recommendations"]
    Guidance --> Plan["6. Draft & edit a smog-safe daily routine or compare transport"]
    Plan --> Confirm["7. Explicitly confirm schedule or log completed action"]
    Confirm --> Follow["8. Configure quiet-hour alerts & join community initiatives"]
```

### Product modules and routes

| Module | Capabilities implemented in the repository | Main UI routes |
| :--- | :--- | :--- |
| **Identity & governance** | Argon2id registration/login, email verification & password reset flows, session inspection/revocation, profile & preference controls, JSON data export, account deletion. | `/login`, `/register`, `/forgot-password`, `/dashboard/settings/*` |
| **Consent-first locations** | Curated city/PIN-prefix gazetteer search, saved locations with `location_precision` (`city`, `postal_code`, `neighborhood`, `exact`), optional voluntary browser geolocation, ownership isolation. | `/dashboard/settings/locations` |
| **Environmental intelligence** | Standard-isolated `india_naqi` & `us_epa` current AQI, 24h/7d/30d Recharts trends, 24h forecast strip & cleaner windows, MapLibre GL station map, weather dispersion context, staleness & fixture banners. | `/air-quality`, `/air-quality/[city]`, `/dashboard/air-quality` |
| **AirWise Copilot & RAG** | Consent-gated Gemini gateway, 12 allowlisted tools, reviewed WHO/EPA/NCDC knowledge retrieval, verified SSE streaming, conversation history & deletion. | `/dashboard/assistant` |
| **Recommendations & routines** | 5-category hybrid daily cards with feedback, plus Morning–Night routine draft generation, slot editing, and explicit confirmation before persistence. | `/dashboard`, `/dashboard/routine-planner` |
| **Indoor air & transport** | Unmeasured-indoor-air guardrails, deterministic room `CADR`/`ACH` calculator, and exposure-screened passenger-km commute comparisons. | `/dashboard/indoor-air`, `/dashboard/transport` |
| **Impact & history** | Self-reported action logging, cumulative avoided-`CO2e`/energy summaries, and chronological activity history. | `/dashboard/impact`, `/dashboard/history` |
| **Smart alerts** | Threshold, severe-smog, forecast-deterioration, clean-window, stale-telemetry, and daily-digest rules with Redis deduplication, cooldowns, and timezone-aware quiet hours. | `/dashboard/alerts` |
| **Neighborhood community** | Coarse-boundary groups, clean-air challenges, opt-in member display names, self-reported aggregate metrics, abuse reporting, and moderator/admin resolution. | `/dashboard/community`, `/admin/community` |
| **Learn hub & admin console** | Public pollution explainers; role-gated admin overview, user management (with self-lockout protection), data-source governance, RAG corpus status, AI token/latency metrics, and redacted audit logs. | `/learn`, `/learn/[slug]`, `/admin/*` |

### System architecture

AirWise uses a **modular monolith**: a Next.js 15 App Router frontend paired with a layered FastAPI backend (`api/v1` -> `services` & `ai/orchestration` -> `repositories` -> `models` + `integrations`), keeping authorization, deterministic math, and transaction boundaries explicit while offloading scheduled ingestion and alert evaluation to Celery workers or authenticated cron jobs.

```mermaid
flowchart TB
    Browser["Browser: Guest & Authenticated Workspaces"]
    UI["Next.js 15 App Router (React 19, Strict TypeScript)"]
    API["FastAPI Modular Monolith (/api/v1, Sessions, CSRF, RBAC, Security Headers)"]
    Domains["Domain Engines: Standard-Isolated AQI, Weather, Safety, Routines, Impact, Alerts, Community"]
    AI["Copilot Pipeline: 12-Tool Allowlist, Hybrid RAG, Guardrails, Verifier, Gemini Gateway"]
    PG[("PostgreSQL 16: Relational + PostGIS + pgvector")]
    Redis[("Redis 7: Stale-Aware Cache, Rate Limits, Token Budgets, Broker")]
    Workers["Celery Worker & Beat Scheduler (or Authenticated Cron)"]
    Environment["Allowlisted HTTPS Providers: OpenAQ, OpenWeather, Open-Meteo"]
    Gemini["Google Gemini: Structured JSON & 768-dim Embeddings"]
    Email["Console Sink or Resend Transactional Email"]

    Browser --> UI
    UI <-->|"Typed JSON & Verified SSE"| API
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

| Layer | Main technologies | Role in the solution |
| :--- | :--- | :--- |
| **Frontend** | Next.js 15, React 19, strict TypeScript | RSC route shells, interactive client workspaces, typed API & SSE clients. |
| **Design & state** | Tailwind CSS, Radix primitives, TanStack Query, Zustand | WCAG 2.2 AA light/dark tokens, stale-aware server cache, lightweight guest location/standard state. |
| **Forms & charts** | React Hook Form, Zod 4, Recharts, MapLibre GL 6 | Client schema validation, null-preserving pollutant charts, spatial station layer with accessible list fallback. |
| **Backend** | Python 3.12+, FastAPI, Pydantic v2 | Versioned `/api/v1` contracts, centralized error envelopes, security middleware. |
| **Persistence** | SQLAlchemy 2.x async, Alembic, PostgreSQL 16 (or SQLite demo) | Ownership-scoped repositories, PostGIS spatial points, `pgvector` embeddings, reversible migrations. |
| **Resilience & workers** | Redis 7, Celery, HTTPX pooled clients | Fresh/stale-backup telemetry caching, sliding-window rate limits, circuit breakers, scheduled tasks. |
| **Quality & testing** | Ruff, MyPy (`--strict`), Pytest, ESLint, Vitest, `axe-core`, Playwright | Static analysis, unit/integration/contract/security/AI-eval suites, WCAG 2.2 AA checks, 13-step Chromium E2E. |

Dependency manifests are authoritative: [backend dependencies](./backend/pyproject.toml) and [frontend dependencies](./frontend/package.json).

### Persistence domains

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

---

## 4. Assumptions made and implementation boundaries

To ensure scientific honesty, safe user decisions, and reproducible evaluation, AirWise AI makes every modeling assumption and implementation boundary explicit:

### Scientific & environmental calculation assumptions

1. **Standard-specific AQI preconditions & truncation:** `us_epa` and `india_naqi` are never mixed or cross-labeled. `india_naqi` requires at least **three** valid pollutants including **`PM2.5` or `PM10`**; if fewer pollutants are reported, overall AQI explicitly returns `null` (`status: "unavailable"`). `us_epa` applies EPA truncation rules (`PM2.5` to `0.1 µg/m³`, `PM10` to integer, `CO` to `0.1 ppm`, `O3` to `0.001 ppm`) prior to piecewise linear interpolation.
2. **Gaseous unit conversion reference state:** When converting gaseous concentrations (`NO2`, `SO2`, `CO`, `O3`) between mass (`µg/m³`, `mg/m³`) and mixing ratio (`ppb`, `ppm`), AirWise assumes standard ambient reference conditions of **25 °C (298.15 K) and 1 atm (101.325 kPa)** (`24.45 L/mol` molar volume). Particulate matter (`PM2.5`, `PM10`) is never converted from `ppb`/`ppm`.
3. **Staleness window:** Ambient observations older than **3 hours** (`10,800 s`) or served from expired fallback cache are flagged `is_stale: true` and accompanied by a visible UI staleness warning.
4. **Deterministic impact assumptions (`is_estimate: true`):**
   - *Transportation `CO2e`:* Uses published regional passenger-km / vehicle-km factors (e.g., India GHG Program / US EPA reference factors seeded via [`reference_factors.py`](./backend/app/services/impact/reference_factors.py)) divided by explicit vehicle occupancy, without double-dividing already passenger-normalized transit factors.
   - *Household electricity:* Multiplies `power_kW * operating_hours * regional_grid_factor` (`india_cea_grid_avg` or `us_epa_egrid_avg`) as a marginal operational estimate rather than smart-meter billing data.
   - *Indoor HEPA filtration:* Models clean-air delivery rate per room volume (`ACH = CADR / (area * ceiling_height)`) assuming a reasonably sealed, well-mixed single room; it does not claim guaranteed indoor `PM2.5` readings or clinical risk percentages.
   - *Relative exposure:* Computes a comparative `PM2.5 * duration * microenvironment_modifier` index rather than individual physiological inhaled dose (which depends on breathing rate and mask fit).
5. **Unmeasured indoor air assumption:** Unless a physical indoor particulate monitor is integrated, indoor air quality is treated and labeled as **unmeasured**—never inferred numerically from outdoor station AQI. Houseplants and ozone-generating cleaners are explicitly excluded as particulate controls.

### Data, privacy, and operational boundaries

- **Live vs. fixture telemetry:** `OpenAQ`, `OpenWeather`, and keyless `Open-Meteo` adapters are implemented; `CPCB` is a regional adapter interface rather than a pre-wired government credentialed feed. Offline/CI runs use the explicit `fixture` provider (`is_development_fixture: true`), which startup validation strictly rejects when `APP_ENV=production`.
- **Supported city gazetteer:** Out-of-the-box city and PIN-prefix lookup covers **10 major Indian urban centers** (Delhi, Gurugram, Noida, Bengaluru, Mumbai, Chennai, Kolkata, Hyderabad, Pune, and Lucknow) without requiring external geocoding keys or browser GPS.
- **User confirmation & privacy:** Schedules, preferences, and community memberships never auto-mutate without user confirmation. Community participation metrics are explicitly labeled as self-reported aggregates with coarse neighborhood labels only.
- **Stubbed external channels:** Email/password auth, console/Resend email, and in-app alerts are implemented end-to-end; Google OAuth token exchange and Web Push delivery are represented as explicit non-blocking stubs.
- **Local SQLite vs. full PostgreSQL/Redis stack:** Lightweight local/CI execution uses SQLite + in-memory fallbacks for deterministic testing, whereas production spatial (`PostGIS`), vector (`pgvector`), and distributed worker (`Celery` + `Redis`) capabilities require the full-service stack.

---

## 5. Evaluation focus areas

The repository is structured and verified directly against the six core engineering evaluation dimensions:

| Focus Area | How AirWise AI delivers and validates it | Key codebase evidence |
| :--- | :--- | :--- |
| **1. Code Quality** | Strict unidirectional modular-monolith layering (`api` -> `services`/`ai` -> `repositories` -> `models`), RSC-first Next.js App Router, zero `any` escapes, `mypy --strict` across 118 Python files, `ruff` (including Bandit `S` & `ASYNC` rules), `eslint --max-warnings=0`, strict `tsc --noEmit`, and 6 Architecture Decision Records. | [`backend/app/`](./backend/app/), [`frontend/src/`](./frontend/src/), [`docs/architecture-decisions/`](./docs/architecture-decisions/) |
| **2. Security** | Argon2id hashing, `HttpOnly` + `SameSite=Lax` cookies, double-submit `X-CSRF-Token` + `Origin`/`Referer` checks, refresh rotation with replay-reuse revocation, repository-level `user_id` IDOR isolation, HTTPS host-allowlist SSRF guard, 12-tool AI allowlist + untrusted RAG delimiters + citation domain allowlist, HTTP security headers (`CSP`, `X-Frame-Options`, `nosniff`, `COOP`, `CORP`, `Permissions-Policy`, `Cache-Control: no-store`), `repr=False` secrets + recursive log redaction, non-root Dockerfiles, and **`0` `npm audit` vulnerabilities**. | [`security.py`](./backend/app/core/security.py), [`middleware.py`](./backend/app/core/middleware.py), [`http_resilience.py`](./backend/app/integrations/http_resilience.py), [`guidance-card.tsx`](./frontend/src/components/assistant/guidance-card.tsx) |
| **3. Efficiency** | Batched SQL `GROUP BY` / `JOIN` queries eliminating `N+1` lookups (`list_stations_in_bbox` runs constant 2 `SELECT`s; batched community & initiative aggregations), memoized `(city, standard)` lookups in batch alert evaluation, loop-scoped pooled `httpx.AsyncClient` & Redis connections, stale-aware Redis cache with bounded `O(1)` local fallback eviction, serverless `NullPool` mode, sliding-window LLM token budgets, and Next.js `optimizePackageImports` + static route prerendering. | [`telemetry_repository.py`](./backend/app/repositories/telemetry_repository.py), [`cache.py`](./backend/app/services/air_quality/cache.py), [`budget.py`](./backend/app/ai/gateway/budget.py), [`next.config.ts`](./frontend/next.config.ts) |
| **4. Testing** | Multi-layer test pyramid: **89 backend Pytest tests** (unit, integration, API contract, security/IDOR/CSRF/SSRF, and the 12-scenario AI safety/grounding evaluation suite), **27 frontend Vitest tests** (Zod schemas, SSE stream state machine, UI flows, null-data chart integrity, and `axe-core` WCAG 2.2 AA checks), and **Playwright Chromium E2E** covering the complete 13-step user journey. | [`backend/tests/`](./backend/tests/), [`frontend/tests/`](./frontend/tests/), [`frontend/e2e/`](./frontend/e2e/), [`ci.yml`](./.github/workflows/ci.yml) |
| **5. Accessibility** | WCAG 2.2 Level AA color tokens (`>= 4.5:1` verified mathematically across both Light and Dark themes), non-color-only `AQIBadge` (symbol + numeric value + category + standard + `role="status"`), universal skip link (`#main-content` across all routes), `:focus-visible` keyboard outlines, `prefers-reduced-motion` & `forced-colors` support, labeled forms (`aria-invalid` + valid `aria-describedby`), `aria-busy` skeletons, `aria-live` streaming status, and automated `axe-core` verification. | [`globals.css`](./frontend/src/app/globals.css), [`aqi-badge.tsx`](./frontend/src/components/air-quality/aqi-badge.tsx), [`accessibility-axe.test.tsx`](./frontend/tests/accessibility-axe.test.tsx) |
| **6. Problem Statement Alignment** |Directly solves daily household smog decision-making by uniting standard-isolated AQI, exposure-first safety overrides, grounded RAG Copilot explanations, editable routine planning, transparent `CO2e`/`CADR` math, smart quiet-hour alerts, and privacy-safe neighborhood challenges under 15 non-negotiable domain invariants. | [`AGENTS.md`](./AGENTS.md), [`docs/prd.md`](./docs/prd.md), [`docs/safety.md`](./docs/safety.md) |

---

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
| `AIR_QUALITY_PROVIDER` | `openaq`, `openweather`, `open_meteo`, `cpcb` interface, or explicit `fixture`. |
| `AIR_QUALITY_FALLBACK_PROVIDER` | `openaq`, `openweather`, `open_meteo` (default keyless model fallback), or `none`. |
| `AIR_QUALITY_API_KEY`, `AIR_QUALITY_FALLBACK_API_KEY` | Provider-specific AQI credentials; primary keys are never leaked to a mismatched fallback provider. |
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
npm audit
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
| Backend unit tests | AQI boundaries, deterministic math, secret redaction, bounded caches, query batching, gateway and domain rules. |
| Integration/contract/security tests | API flows, persistence behavior, RBAC/IDOR/CSRF/SSRF defenses, security headers, and error contracts. |
| AI evaluations | 12-scenario safety, grounding, prompt-injection, citation/number validation and deterministic fallback harness. |
| Vitest & `axe-core` | UI behavior, AQI standard isolation, null-preserving charts, assistant SSE streaming, WCAG 2.2 AA `axe-core` rules, and light/dark token contrast ratios (`>= 4.5:1`). |
| Playwright | Chromium browser scenarios including the full-stack 13-step user journey, assistant streaming UI, and select control layout. |
| CI | Backend Ruff/MyPy/Pytest, Frontend ESLint/TypeScript/Vitest/Next build, full-stack 13-step Playwright E2E, and Docker image builds. |

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
