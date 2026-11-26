from __future__ import annotations

from httpx import AsyncClient


def _extract_auth_cookies(client: AsyncClient) -> tuple[str, str]:
    return (
        client.cookies.get("airwise_session", ""),
        client.cookies.get("airwise_csrf", ""),
    )


async def test_csrf_and_untrusted_origin_rejection(api_client: AsyncClient) -> None:
    await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": "csrf-user@example.com",
            "password": "SafePassword2026",
            "display_name": "CSRF Tester",
        },
    )

    # Missing X-CSRF-Token header on state-changing endpoint -> 403 AUTH_CSRF_INVALID
    no_csrf = await api_client.patch(
        "/api/v1/users/me",
        json={"profile": {"display_name": "Attacker"}},
    )
    assert no_csrf.status_code == 403
    assert no_csrf.json()["error"]["code"] == "AUTH_CSRF_INVALID"

    # Valid CSRF header but untrusted Origin -> 403 AUTH_CSRF_INVALID
    bad_origin = await api_client.patch(
        "/api/v1/users/me",
        headers={
            "X-CSRF-Token": api_client.cookies.get("airwise_csrf", ""),
            "Origin": "https://malicious.example.org",
        },
        json={"profile": {"display_name": "Attacker"}},
    )
    assert bad_origin.status_code == 403
    assert bad_origin.json()["error"]["code"] == "AUTH_CSRF_INVALID"


async def test_cross_user_idor_location_and_session_isolation(api_client: AsyncClient) -> None:
    # Register User A and create a saved location
    await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": "alice@example.com",
            "password": "AliceSecure2026",
            "display_name": "Alice",
        },
    )
    alice_session, alice_csrf = _extract_auth_cookies(api_client)
    alice_loc_res = await api_client.post(
        "/api/v1/locations",
        headers={"X-CSRF-Token": alice_csrf, "Origin": "http://localhost:3000"},
        json={
            "label": "home",
            "display_name": "Alice Home",
            "city": "Delhi",
            "country_code": "IN",
            "location_precision": "city",
            "timezone": "Asia/Kolkata",
            "is_primary": True,
        },
    )
    alice_location_id = alice_loc_res.json()["data"]["id"]
    alice_sessions_res = await api_client.get("/api/v1/auth/sessions")
    alice_session_id = alice_sessions_res.json()["data"][0]["id"]

    # Register User B (switches cookies on client)
    api_client.cookies.clear()
    await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": "bob@example.com",
            "password": "BobSecurePass2026",
            "display_name": "Bob",
        },
    )
    _, bob_csrf = _extract_auth_cookies(api_client)
    bob_headers = {"X-CSRF-Token": bob_csrf, "Origin": "http://localhost:3000"}

    # Bob cannot see, update, or delete Alice's location (returns 404 to avoid existence leak)
    bob_list = await api_client.get("/api/v1/locations")
    assert bob_list.json()["data"] == []

    bob_patch_alice = await api_client.patch(
        f"/api/v1/locations/{alice_location_id}",
        headers=bob_headers,
        json={"display_name": "Hijacked"},
    )
    assert bob_patch_alice.status_code == 404

    bob_del_alice = await api_client.delete(
        f"/api/v1/locations/{alice_location_id}",
        headers=bob_headers,
    )
    assert bob_del_alice.status_code == 404

    # Bob cannot revoke Alice's browser session
    bob_revoke_alice = await api_client.delete(
        f"/api/v1/auth/sessions/{alice_session_id}",
        headers=bob_headers,
    )
    assert bob_revoke_alice.status_code == 404

    # Regular user Bob cannot access /api/v1/admin/status -> 403 AUTH_FORBIDDEN
    bob_admin = await api_client.get("/api/v1/admin/status")
    assert bob_admin.status_code == 403
    assert bob_admin.json()["error"]["code"] == "AUTH_FORBIDDEN"

    # Alice's session remains intact
    api_client.cookies.set("airwise_session", alice_session)
    alice_check = await api_client.get("/api/v1/locations")
    assert len(alice_check.json()["data"]) == 1


async def test_rotated_session_reuse_detection_invalidates_all_sessions(
    api_client: AsyncClient,
) -> None:
    await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": "reuse@example.com",
            "password": "ReuseGuard2026",
            "display_name": "Reuse Guard",
        },
    )
    initial_token, csrf = _extract_auth_cookies(api_client)
    headers = {"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"}

    # Legitimate rotation issues a second session token
    rot_res = await api_client.post("/api/v1/auth/refresh", headers=headers)
    assert rot_res.status_code == 200
    rotated_token, rotated_csrf = _extract_auth_cookies(api_client)
    assert rotated_token != initial_token

    # Replay the already-rotated initial_token -> triggers reuse detection & revokes all sessions
    api_client.cookies.set("airwise_session", initial_token)
    api_client.cookies.set("airwise_csrf", rotated_csrf)
    replay_res = await api_client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": rotated_csrf, "Origin": "http://localhost:3000"},
    )
    assert replay_res.status_code == 401
    assert replay_res.json()["error"]["code"] == "AUTH_SESSION_EXPIRED"

    # Even the previously valid rotated_token is now revoked
    api_client.cookies.set("airwise_session", rotated_token)
    me_after_replay = await api_client.get("/api/v1/users/me")
    assert me_after_replay.status_code == 401


async def test_vercel_cron_endpoint_enforces_bearer_secret(api_client: AsyncClient) -> None:
    unauth = await api_client.get("/api/v1/system/cron/daily-maintenance")
    assert unauth.status_code == 403

    wrong = await api_client.get(
        "/api/v1/system/cron/daily-maintenance",
        headers={"Authorization": "Bearer wrong-secret"},
    )
    assert wrong.status_code == 403

    ok = await api_client.get(
        "/api/v1/system/cron/daily-maintenance",
        headers={"Authorization": "Bearer test-cron-secret-value-123456"},
    )
    assert ok.status_code == 200
    assert ok.json()["data"]["status"] == "completed"
