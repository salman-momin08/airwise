# API Contract Specification: AirWise AI (`api.md`)

All business endpoints are versioned under `/api/v1/`. System liveness, readiness, and internal metrics live at root operational paths.

---

## 1. Standard Response & Error Envelopes

### Success Envelope (`200 OK`, `201 Created`)
```json
{
  "data": {},
  "meta": {
    "request_id": "9f8c6c9a-31f9-4e14-9a4e-57f07c7e2f19",
    "timestamp": "2026-11-19T09:15:00Z",
    "pagination": {
      "cursor": "eyJpZCI6IjEyMyJ9",
      "has_more": false,
      "limit": 20
    }
  }
}
```

### Error Envelope (`4xx`, `5xx`)
```json
{
  "error": {
    "code": "AIR_QUALITY_PROVIDER_UNAVAILABLE",
    "message": "Current air quality data is temporarily unavailable.",
    "request_id": "9f8c6c9a-31f9-4e14-9a4e-57f07c7e2f19"
  }
}
```

### Standard Error Codes
- `AUTH_INVALID_CREDENTIALS` (`401`) · `AUTH_SESSION_EXPIRED` (`401`) · `AUTH_CSRF_INVALID` (`403`) · `AUTH_FORBIDDEN` (`403`)
- `RATE_LIMIT_EXCEEDED` (`429`) · `AI_DAILY_BUDGET_EXCEEDED` (`429`)
- `VALIDATION_ERROR` (`422`) · `RESOURCE_NOT_FOUND` (`404`) · `CONFLICT` (`409`)
- `AIR_QUALITY_PROVIDER_UNAVAILABLE` (`503`) · `AQI_CALCULATION_UNAVAILABLE` (`200` with `status: "unavailable"` in data)
- `AI_PROVIDER_UNAVAILABLE` (`503` when deterministic fallback is not applicable)

---

## 2. Endpoint Catalog & Authorization Matrix

### Assistant request and streaming contract

Both chat POST endpoints accept `message` (1-2000 characters), optional `conversation_id`,
optional coarse `city`, `standard` (`india_naqi` or `us_epa`), required explicit
`ai_consent: true`, and optional `use_preferences: true`. Unknown request fields are rejected.
An optional discriminated `calculation` object (`kind: transport` or `kind: exposure`)
accepts explicitly supplied factors/assumptions for the existing deterministic calculators;
the model cannot invent calculation arguments. See OpenAPI for the full input schemas.

Non-streaming results contain `conversation_id` / `message_id` (null when history is disabled),
`structured_response`, canonical `citations`, `generation` metadata and `tools_used`.
The eight guidance fields are `situation_summary`, `environmental_conditions`,
`recommended_action`, `why_this_helps`, `estimated_impact`, `uncertainty_or_limitations`,
`safer_alternative`, and `evidence_references`.

Streaming emits SSE `status`, validated `delta`, terminal `complete`, or terminal `error`
frames. Each frame has `request_id`. `complete` contains the same result fields as non-streaming
chat, without an additional `data` wrapper. Clients must not treat a disconnected stream or
partial deltas as a successful response. Authentication, CSRF, ownership and consent checks
occur before streaming headers are sent.

Missing Gemini credentials, missing evidence, stale data and output-verification failures
return explicitly labeled safe guidance with `generation.is_fallback: true` and a reason code;
they never masquerade as successful model generation. Daily quota violations are errors.

| Domain | Method & Path | Min Role | CSRF | Purpose |
| :--- | :--- | :--- | :---: | :--- |
| **Auth** | `POST /api/v1/auth/register` | Guest | No | Register email/password account (Argon2id) |
| | `POST /api/v1/auth/login` | Guest | No | Issue `HttpOnly` session + CSRF cookie |
| | `POST /api/v1/auth/logout` | User | Yes | Revoke current session & clear cookies |
| | `POST /api/v1/auth/refresh` | User | Yes | Rotate session/refresh token |
| | `POST /api/v1/auth/forgot-password` | Guest | No | Trigger rate-limited reset token email |
| | `POST /api/v1/auth/reset-password` | Guest | No | Complete password reset & revoke old sessions |
| | `POST /api/v1/auth/verify-email` | Guest | No | Consume single-use email verification token |
| | `GET /api/v1/auth/me` | Guest / User | No | Return current session principal & roles (`guest` when unauthenticated) |
| | `GET /api/v1/auth/sessions` | User | No | List active unrevoked browser sessions |
| | `DELETE /api/v1/auth/sessions/{session_id}` | User (Owner) | Yes | Revoke a specific active session |
| | `POST /api/v1/auth/sessions/revoke-others` | User | Yes | Revoke all active sessions except current |
| | `GET /api/v1/auth/oauth/google/status` | Guest | No | Inspect optional Google OAuth 2.0 adapter availability |
| **Users** | `GET /api/v1/users/me` | User | No | Retrieve profile & consented preferences |
| | `PATCH /api/v1/users/me` | User | Yes | Update profile / household preferences |
| | `DELETE /api/v1/users/me` | User | Yes | Self-service account & PII deletion |
| | `GET /api/v1/users/me/export` | User | No | Export portable JSON archive of user data |
| **Locations** | `GET /api/v1/locations` | User | No | List user's saved locations |
| | `POST /api/v1/locations` | User | Yes | Create saved location (`Home`, `School`, etc.) |
| | `PATCH /api/v1/locations/{id}` | User (Owner) | Yes | Update saved location or primary flag |
| | `DELETE /api/v1/locations/{id}` | User (Owner) | Yes | Remove saved location |
| | `GET /api/v1/locations/search` | Guest | No | Search city / postal code gazetteer |
| **Air Quality** | `GET /api/v1/air-quality/current` | Guest | No | Current normalized pollutants + standard AQI |
| | `GET /api/v1/air-quality/history` | Guest | No | 24h / 7d / 30d verified historical series |
| | `GET /api/v1/air-quality/forecast` | Guest | No | Hourly/daily pollution forecast with provenance |
| | `GET /api/v1/air-quality/stations` | Guest | No | Nearby monitoring stations (PostGIS radius) |
| | `GET /api/v1/air-quality/map` | Guest | No | GeoJSON station layer for bounding box |
| **Weather** | `GET /api/v1/weather/current` | Guest | No | Current meteorology & winter inversion stagnation context |
| **Assistant** | `POST /api/v1/assistant/chat` | User | Yes | Non-streaming grounded AirWise Copilot turn |
| | `POST /api/v1/assistant/chat/stream` | User | Yes | SSE streaming Copilot turn with tool events |
| | `GET /api/v1/assistant/conversations` | User | No | List user's chat threads |
| | `GET /api/v1/assistant/conversations/{id}/messages` | User (Owner) | No | Fetch latest 100 conversation messages & citations |
| | `DELETE /api/v1/assistant/conversations` | User | Yes | Delete all owned chat history and generation metadata |
| | `DELETE /api/v1/assistant/conversations/{id}` | User (Owner) | Yes | Delete conversation history |
| | `POST /api/v1/assistant/feedback` (planned) | User | Yes | Future helpfulness/safety feedback on reply |
| **Recommendations** | `POST /api/v1/recommendations/generate` | User | Yes | Run hybrid deterministic + GenAI engine |
| | `GET /api/v1/recommendations/today` | User | No | Fetch active prioritized daily cards |
| | `POST /api/v1/recommendations/{id}/feedback` | User (Owner) | Yes | Record completed/dismissed/helpful state |
| **Routines** | `POST /api/v1/routines/generate` | User | Yes | Generate Morning–Night smog-safe schedule |
| | `GET /api/v1/routines` | User | No | List saved daily routines |
| | `GET /api/v1/routines/{id}` | User (Owner) | No | Inspect routine & activity slots |
| | `PATCH /api/v1/routines/{id}` | User (Owner) | Yes | Confirm/edit routine activities |
| | `DELETE /api/v1/routines/{id}` | User (Owner) | Yes | Delete saved routine |
| **Impact** | `POST /api/v1/impact/calculate` | Guest / User | Conditional | Run deterministic transport/energy/filtration/exposure math |
| | `GET /api/v1/impact/summary` | User | No | Aggregate avoided CO2e, actions & cost estimates |
| | `GET /api/v1/impact/history` | User | No | Time-series of logged user actions & estimates |
| **Alerts** | `GET /api/v1/alerts` | User | No | List configured smart alert rules |
| | `POST /api/v1/alerts` | User | Yes | Create AQI/forecast/window alert rule |
| | `PATCH /api/v1/alerts/{id}` | User (Owner) | Yes | Update threshold, quiet hours, or toggle |
| | `DELETE /api/v1/alerts/{id}` | User (Owner) | Yes | Delete alert rule |
| | `GET /api/v1/notifications` | User | No | Paginated in-app & delivery history |
| **Community** | `GET /api/v1/communities` | Guest / User | No | Discover neighborhood clean-air groups |
| | `POST /api/v1/communities` | Moderator/Admin | Yes | Create moderated neighborhood group |
| | `GET /api/v1/communities/{id}` | Guest / User | No | View aggregate community dashboard |
| | `POST /api/v1/communities/{id}/join` | User | Yes | Join neighborhood group |
| | `POST /api/v1/communities/{id}/leave` | User | Yes | Leave neighborhood group |
| | `GET /api/v1/communities/{id}/initiatives` | Guest / User | No | List active clean-air challenges |
| | `POST /api/v1/communities/{id}/initiatives` | Moderator/Admin | Yes | Launch community challenge |
| **Admin** | `/api/v1/admin/*` | Admin | Yes | Users, data sources, RAG corpus, AI telemetry, moderation, audit logs |
| **System** | `GET /health/live` | Public | No | Process liveness probe |
| | `GET /health/ready` | Public | No | DB + Redis readiness probe |
| | `GET /metrics` | Internal / Token | No | Prometheus metrics scrape endpoint |
| | `GET /api/v1/system/cron/daily-maintenance` | Internal (`CRON_SECRET`) | No | Vercel Cron daily session retention & telemetry refresh trigger |
| | `GET /api/v1/system/cron/ingest-air-quality` | Internal (`CRON_SECRET`) | No | Scheduled priority-city AQI station & cache ingestion trigger |

---

## 3. SSE Streaming Contract (`POST /api/v1/assistant/chat/stream`)

Content-Type: `text/event-stream; charset=utf-8` (`Cache-Control: no-cache`, `X-Accel-Buffering: no`)

```text
event: status
data: {"request_id":"...","stage":"tool_execution","tool":"get_current_air_quality","status":"running"}

event: delta
data: {"request_id":"...","field":"situation_summary","delta":"PM2.5 in New Delhi is currently elevated..."}

event: complete
data: {"request_id":"...","conversation_id":"...","message_id":"...","response":{...},"citations":[...]}

event: error
data: {"request_id":"...","code":"AI_PROVIDER_TIMEOUT","message":"..."}
```
