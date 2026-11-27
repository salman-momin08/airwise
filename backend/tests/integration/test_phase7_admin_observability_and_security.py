from __future__ import annotations

import time
import uuid

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models.identity import User


def _csrf(client: AsyncClient) -> dict[str, str]:
    return {
        "X-CSRF-Token": client.cookies.get("airwise_csrf") or "",
        "Origin": "http://localhost:3000",
    }


async def _register(client: AsyncClient, email: str, name: str) -> uuid.UUID:
    res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Phase7AdminSecurePass2026",
            "display_name": name,
        },
    )
    assert res.status_code == 201
    return uuid.UUID(str(res.json()["data"]["user_id"]))


async def test_admin_rbac_self_lockout_guard_session_revocation_and_audit_redaction(
    api_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    # 1. Guest and standard user are blocked from all /api/v1/admin/* governance endpoints
    for path in (
        "/api/v1/admin/overview",
        "/api/v1/admin/users",
        "/api/v1/admin/data-sources",
        "/api/v1/admin/knowledge-base",
        "/api/v1/admin/ai-monitoring",
        "/api/v1/admin/audit-logs",
        "/api/v1/admin/settings",
    ):
        assert (await api_client.get(path)).status_code == 401

    regular_id = await _register(api_client, "member@example.com", "Regular User")
    regular_session = api_client.cookies.get("airwise_session") or ""
    for path in (
        "/api/v1/admin/overview",
        "/api/v1/admin/users",
        "/api/v1/admin/data-sources",
        "/api/v1/admin/audit-logs",
    ):
        assert (await api_client.get(path)).status_code == 403

    # 2. Promote a dedicated Admin account
    api_client.cookies.clear()
    admin_id = await _register(api_client, "ops-admin@example.com", "Platform Admin")
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        await session.execute(update(User).where(User.id == admin_id).values(role="admin"))
        await session.commit()

    ov_res = await api_client.get("/api/v1/admin/overview")
    assert ov_res.status_code == 200
    assert ov_res.json()["data"]["active_users_count"] == 2

    # 3. Self-lockout guard prevents admin from suspending or demoting their own account
    self_demote = await api_client.patch(
        f"/api/v1/admin/users/{admin_id}",
        headers=_csrf(api_client),
        json={"role": "user"},
    )
    assert self_demote.status_code == 409

    self_suspend = await api_client.patch(
        f"/api/v1/admin/users/{admin_id}",
        headers=_csrf(api_client),
        json={"is_active": False},
    )
    assert self_suspend.status_code == 409

    # 4. Admin suspends regular_id -> revokes regular_id's active sessions immediately
    suspend_res = await api_client.patch(
        f"/api/v1/admin/users/{regular_id}",
        headers=_csrf(api_client),
        json={"is_active": False},
    )
    assert suspend_res.status_code == 200
    assert suspend_res.json()["data"]["is_active"] is False

    # 5. Seed data sources, toggle one, and upsert a system setting with sensitive-key redaction
    seed_src = await api_client.post(
        "/api/v1/admin/data-sources/seed-defaults",
        headers=_csrf(api_client),
    )
    assert seed_src.status_code == 200
    sources = seed_src.json()["data"]
    assert len(sources) == 3

    toggle_src = await api_client.patch(
        f"/api/v1/admin/data-sources/{sources[1]['id']}",
        headers=_csrf(api_client),
        json={"is_enabled": False, "priority_rank": 5},
    )
    assert toggle_src.status_code == 200
    assert toggle_src.json()["data"]["is_enabled"] is False

    put_setting = await api_client.put(
        "/api/v1/admin/settings/platform_notice",
        headers=_csrf(api_client),
        json={"value": {"banner": "Smog season advisory", "gemini_api_key": "accidental-secret"}},
    )
    assert put_setting.status_code == 200
    assert put_setting.json()["data"]["value"]["gemini_api_key"] == "[REDACTED]"

    # Inspect knowledge governance, AI monitoring, and filtered audit logs
    assert (await api_client.get("/api/v1/admin/knowledge-base")).status_code == 200
    assert (await api_client.get("/api/v1/admin/ai-monitoring")).status_code == 200
    audit_res = await api_client.get("/api/v1/admin/audit-logs?action_prefix=admin.")
    assert audit_res.status_code == 200
    audit_actions = {entry["action"] for entry in audit_res.json()["data"]}
    assert {
        "admin.user_updated",
        "admin.data_sources_seeded",
        "admin.data_source_updated",
        "admin.system_setting_updated",
    }.issubset(audit_actions)

    # Verify suspended user's previous session cookie is rejected (401)
    api_client.cookies.set("airwise_session", regular_session)
    assert (await api_client.get("/api/v1/users/me")).status_code == 401


async def test_readiness_security_headers_prometheus_metrics_and_cached_aqi_latency_budget(
    api_client: AsyncClient,
) -> None:
    live = await api_client.get("/health/live")
    assert live.status_code == 200
    assert live.headers["X-Content-Type-Options"] == "nosniff"
    assert live.headers["X-Frame-Options"] == "DENY"
    assert "geolocation=(self)" in live.headers["Permissions-Policy"]

    ready = await api_client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["checks"]["database"] == "ok"

    # Prime cache on first request, then benchmark cached AQI p95 (< 300ms target)
    first_aqi = await api_client.get("/api/v1/air-quality/current?city=Delhi&standard=india_naqi")
    assert first_aqi.status_code == 200

    cached_samples_ms: list[float] = []
    for _ in range(15):
        t0 = time.perf_counter()
        res = await api_client.get("/api/v1/air-quality/current?city=Delhi&standard=india_naqi")
        cached_samples_ms.append((time.perf_counter() - t0) * 1000.0)
        assert res.status_code == 200

    sorted_samples = sorted(cached_samples_ms)
    p95_cached_ms = sorted_samples[round(0.95 * (len(sorted_samples) - 1))]
    assert p95_cached_ms < 300.0

    metrics_res = await api_client.get("/metrics")
    assert metrics_res.status_code == 200
    metrics_text = metrics_res.text
    assert "airwise_http_latency_p95_ms" in metrics_text
    assert "airwise_aqi_cache_hits_total" in metrics_text
