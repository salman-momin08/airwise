# Privacy & Data Governance Specification (`privacy.md`)

AirWise AI is built on **data minimization, explicit consent, coarse-by-default location intelligence, and full user control** aligned with GDPR and India's Digital Personal Data Protection (DPDP) principles.

---

## 1. Geolocation & Spatial Privacy

1. **Zero Automatic Geolocation:** Browser geolocation is never requested on initial load; users trigger it voluntarily or use city/postal search with full feature parity.
2. **Minimum Precision Storage:** `saved_locations` records `location_precision` (`city`, `postal_code`, `neighborhood`, `exact`). Users who select a city store `coordinates = NULL` (or city centroid marked `precision = 'city'`).
3. **LLM Data Boundary:** Exact latitude/longitude, street names, email addresses, and user IDs are **never** sent to external LLM APIs. Only coarse city/region labels, timezone, and consented household preferences are included in prompt context.
4. **Community Privacy:** Neighborhood dashboards aggregate participation at the community level and never display household pins or individual names unless `public_display_consent = true`.

---

## 2. Health-Adjacent & Household Preferences

- All profile attributes (`age_category`, `has_vulnerable_members`, `cooking_type`, `has_hepa_purifier`, `budget_tier`) are optional and editable/removable at any time under `/dashboard/settings/privacy`.
- AirWise AI intentionally avoids collecting medical diagnoses, prescriptions, or national ID numbers.

---

## 3. Chat History, Logging & Retention Controls

- **User-Controlled Conversations:** Users can delete individual conversations (`DELETE /api/v1/assistant/conversations/{id}`) or disable persistent chat history in privacy settings.
- **Zero Sensitive Prompt Logging by Default:** Production structured logs record `request_id`, latency, model version, and token counts—never raw user chat prompts, cookies, or passwords.
- **Self-Service Export & Erasure:**
  - `GET /api/v1/users/me/export` produces a machine-readable JSON bundle of profile, preferences, saved locations, routines, actions, alerts, and chat history.
  - `DELETE /api/v1/users/me` permanently deletes personal records, revokes active sessions, and anonymizes audit-trail actor references.
