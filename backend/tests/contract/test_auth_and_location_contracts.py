from __future__ import annotations

from httpx import AsyncClient


async def test_api_v1_envelopes_and_vercel_entrypoint_export(api_client: AsyncClient) -> None:
    # Verify standardized success envelope on /api/v1/auth/me
    res = await api_client.get("/api/v1/auth/me", headers={"X-Request-ID": "bad-uuid"})
    assert res.status_code == 200
    body = res.json()
    assert "data" in body and "meta" in body
    assert "request_id" in body["meta"] and "timestamp" in body["meta"]

    # Verify standardized error envelope on validation failure
    bad = await api_client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "short", "display_name": "A"},
    )
    assert bad.status_code == 422
    err_body = bad.json()
    assert err_body["error"]["code"] == "VALIDATION_ERROR"
    assert "request_id" in err_body["error"]

    # Verify OpenAPI documents all auth, user, location & Vercel Cron routes
    openapi = (await api_client.get("/openapi.json")).json()
    paths = set(openapi["paths"].keys())
    expected_paths = {
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/auth/refresh",
        "/api/v1/auth/forgot-password",
        "/api/v1/auth/reset-password",
        "/api/v1/auth/me",
        "/api/v1/users/me",
        "/api/v1/users/me/export",
        "/api/v1/locations",
        "/api/v1/locations/search",
        "/api/v1/system/cron/daily-maintenance",
    }
    assert expected_paths.issubset(paths)
