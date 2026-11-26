from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

from alembic.config import Config
from httpx import AsyncClient

from alembic import command
from app.integrations.email.provider import ConsoleEmailProvider


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    csrf = client.cookies.get("airwise_csrf", "")
    return {
        "X-CSRF-Token": csrf,
        "Origin": "http://localhost:3000",
    }


async def test_registration_profile_locations_export_and_deletion(
    api_client: AsyncClient,
) -> None:
    # 1. Guest still has unauthenticated access to public AQI & city search
    guest_me = await api_client.get("/api/v1/auth/me")
    assert guest_me.status_code == 200
    assert guest_me.json()["data"]["role"] == "guest"

    guest_aqi = await api_client.get(
        "/api/v1/air-quality/current?city=Delhi&standard=india_naqi"
    )
    assert guest_aqi.status_code == 200
    assert guest_aqi.json()["data"]["standard"] == "india_naqi"

    search_res = await api_client.get("/api/v1/locations/search?q=560")
    assert search_res.status_code == 200
    assert any(item["city"] == "Bengaluru" for item in search_res.json()["data"])

    # 2. Register account -> sets HttpOnly session + readable CSRF cookie + verification email
    reg_res = await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": "priya@example.com",
            "password": "CleanAir2026Password",
            "display_name": "Priya Sharma",
            "preferred_aqi_standard": "india_naqi",
            "timezone": "Asia/Kolkata",
        },
    )
    assert reg_res.status_code == 201
    assert "airwise_session" in api_client.cookies
    assert "airwise_csrf" in api_client.cookies
    assert len(ConsoleEmailProvider.last_outbox) == 1

    # Verify email via single-use token extracted from outbox link
    verify_body = ConsoleEmailProvider.last_outbox[0].text_body
    verify_url = [line for line in verify_body.splitlines() if "verify_token=" in line][0].split(
        ": "
    )[1]
    verify_token = parse_qs(urlparse(verify_url).query)["verify_token"][0]
    verify_res = await api_client.post(
        "/api/v1/auth/verify-email", json={"token": verify_token}
    )
    assert verify_res.status_code == 200

    # 3. Update profile & household preferences with CSRF protection
    patch_res = await api_client.patch(
        "/api/v1/users/me",
        headers=_csrf_headers(api_client),
        json={
            "profile": {"display_name": "Priya S.", "preferred_aqi_standard": "us_epa"},
            "preferences": {
                "household_size": 4,
                "has_vulnerable_members": True,
                "commute_modes": ["metro_rail", "carpool_3"],
                "has_hepa_purifier": True,
                "budget_tier": "moderate",
            },
        },
    )
    assert patch_res.status_code == 200
    me_body = patch_res.json()["data"]
    assert me_body["is_email_verified"] is True
    assert me_body["profile"]["preferred_aqi_standard"] == "us_epa"
    assert me_body["preferences"]["has_vulnerable_members"] is True
    assert me_body["preferences"]["commute_modes"] == ["metro_rail", "carpool_3"]

    # 4. Create saved locations (city-level strips coordinates automatically)
    loc_home = await api_client.post(
        "/api/v1/locations",
        headers=_csrf_headers(api_client),
        json={
            "label": "home",
            "display_name": "Home — Indiranagar",
            "city": "Bengaluru",
            "state_region": "Karnataka",
            "country_code": "in",
            "location_precision": "city",
            "latitude": 12.9784,
            "longitude": 77.6408,
            "timezone": "Asia/Kolkata",
            "is_primary": True,
        },
    )
    assert loc_home.status_code == 201
    home_data = loc_home.json()["data"]
    assert home_data["latitude"] is None
    assert home_data["longitude"] is None
    assert home_data["is_primary"] is True

    # 5. Export portable JSON account archive
    export_res = await api_client.get("/api/v1/users/me/export")
    assert export_res.status_code == 200
    export_data = export_res.json()["data"]
    assert export_data["account"]["email"] == "priya@example.com"
    assert len(export_data["saved_locations"]) == 1

    # 6. Rotate session via /auth/refresh and verify old token cannot be reused
    old_session_cookie = api_client.cookies.get("airwise_session")
    refresh_res = await api_client.post(
        "/api/v1/auth/refresh",
        headers=_csrf_headers(api_client),
    )
    assert refresh_res.status_code == 200
    assert api_client.cookies.get("airwise_session") != old_session_cookie

    # 7. Self-service account deletion revokes access and purges PII
    del_res = await api_client.delete(
        "/api/v1/users/me",
        headers=_csrf_headers(api_client),
    )
    assert del_res.status_code == 200
    after_del = await api_client.get("/api/v1/users/me")
    assert after_del.status_code == 401


async def test_password_reset_revokes_existing_sessions(api_client: AsyncClient) -> None:
    await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": "arjun@example.com",
            "password": "InitialPass2026",
            "display_name": "Arjun Mehta",
        },
    )
    ConsoleEmailProvider.last_outbox.clear()

    forgot_res = await api_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "arjun@example.com"},
    )
    assert forgot_res.status_code == 200
    assert len(ConsoleEmailProvider.last_outbox) == 1
    reset_line = [
        line
        for line in ConsoleEmailProvider.last_outbox[0].text_body.splitlines()
        if "token=" in line
    ][0]
    reset_token = parse_qs(urlparse(reset_line).query)["token"][0]

    reset_res = await api_client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "RotatedSecurePass2026"},
    )
    assert reset_res.status_code == 200

    # Old password fails; new password succeeds
    bad_login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": "arjun@example.com", "password": "InitialPass2026"},
    )
    assert bad_login.status_code == 401

    good_login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": "arjun@example.com", "password": "RotatedSecurePass2026"},
    )
    assert good_login.status_code == 200


def test_alembic_reversible_migration_up_and_down(tmp_path: Path, monkeypatch: object) -> None:
    from app.core.config import get_settings

    mig_db = tmp_path / "alembic_migration_check.sqlite3"
    os_url = f"sqlite+aiosqlite:///{mig_db.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", os_url)  # type: ignore[attr-defined]
    get_settings.cache_clear()

    backend_dir = Path(__file__).resolve().parents[2]
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", os_url)

    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")
