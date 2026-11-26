from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.ai.gateway.gemini import OutputModel
from app.ai.rag.knowledge import KnowledgeService
from app.ai.tools.executor import ToolExecutor
from app.core.config import Settings
from app.integrations.email.provider import ConsoleEmailProvider
from app.models.community_alerts import (
    AlertRule,
    CommunityMember,
    CommunityParticipation,
    Notification,
)
from app.models.identity import AuditLog, User
from app.schemas.assistant import ChatRequest, ToolCall
from app.services.air_quality.aqi_calculator import AQIStandard
from app.services.alerts.alert_service import SmartAlertService


def _csrf(client: AsyncClient) -> dict[str, str]:
    return {
        "X-CSRF-Token": client.cookies.get("airwise_csrf", ""),
        "Origin": "http://localhost:3000",
    }


async def _register(
    client: AsyncClient, email: str, display_name: str = "Test Resident"
) -> uuid.UUID:
    res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Phase6SecurePassword2026",
            "display_name": display_name,
            "preferred_aqi_standard": "india_naqi",
        },
    )
    assert res.status_code == 201
    return uuid.UUID(str(res.json()["data"]["user_id"]))


class _StubGateway:
    model_name = "gemini-stub"
    token_usage = 0

    async def generate(
        self, *, system: str, prompt: str, schema: type[OutputModel]
    ) -> OutputModel:
        raise AssertionError("Not called in tool executor test.")

    async def embed(
        self, text: str, *, task: Literal["RETRIEVAL_QUERY", "RETRIEVAL_DOCUMENT"]
    ) -> list[float]:
        return [1.0] + [0.0] * 767


async def test_alert_deduplication_quiet_hours_opt_out_and_idor_isolation(
    api_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    user_id = await _register(api_client, "alerts-user@example.com", "Meera Nair")
    ConsoleEmailProvider.last_outbox.clear()

    # 1. Create alert rule with quiet hours 22:00–07:00 Asia/Kolkata
    rule_res = await api_client.post(
        "/api/v1/alerts",
        headers=_csrf(api_client),
        json={
            "city": "Delhi",
            "alert_type": "aqi_threshold",
            "aqi_standard": "india_naqi",
            "threshold_value": 200,
            "channels": ["in_app", "email"],
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "07:00",
            "cooldown_minutes": 180,
            "timezone": "Asia/Kolkata",
        },
    )
    assert rule_res.status_code == 201
    rule_id = rule_res.json()["data"]["id"]

    # 2. Evaluate OUTSIDE quiet hours (09:00 UTC == 14:30 IST) -> triggers 1 notification + 1 email
    test_settings = Settings(
        app_env="test",
        auth_secret_key="test-only-cryptographic-random-secret-key-at-least-32-bytes",
    )
    daytime_utc = datetime(2026, 11, 26, 9, 0, tzinfo=UTC)
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        svc = SmartAlertService(session=session, settings=test_settings)
        first_eval = await svc.evaluate_active_rules(
            user_id=user_id, evaluation_time=daytime_utc
        )
        assert first_eval.triggered_notifications == 1
        assert first_eval.suppressed_quiet_hours_deliveries == 0
        assert len(ConsoleEmailProvider.last_outbox) == 1

        # 3. Re-evaluate 10m and 4h later while Delhi AQI is unchanged -> 0 duplicate spam!
        second_eval = await svc.evaluate_active_rules(
            user_id=user_id, evaluation_time=daytime_utc + timedelta(minutes=10)
        )
        assert second_eval.triggered_notifications == 0
        assert second_eval.suppressed_duplicates_or_cooldown == 1

        third_eval = await svc.evaluate_active_rules(
            user_id=user_id, evaluation_time=daytime_utc + timedelta(hours=4)
        )
        assert third_eval.triggered_notifications == 0
        assert third_eval.suppressed_duplicates_or_cooldown == 1
        assert len(ConsoleEmailProvider.last_outbox) == 1

    # 4. Evaluate second rule INSIDE quiet hours (20:00 UTC == 01:30 IST) -> email suppressed!
    quiet_rule_res = await api_client.post(
        "/api/v1/alerts",
        headers=_csrf(api_client),
        json={
            "city": "Delhi",
            "alert_type": "severe_smog_episode",
            "aqi_standard": "india_naqi",
            "channels": ["in_app", "email"],
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "07:00",
            "cooldown_minutes": 120,
            "timezone": "Asia/Kolkata",
        },
    )
    assert quiet_rule_res.status_code == 201
    ConsoleEmailProvider.last_outbox.clear()

    overnight_utc = datetime(2026, 11, 26, 20, 0, tzinfo=UTC)
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        svc = SmartAlertService(session=session, settings=test_settings)
        quiet_eval = await svc.evaluate_active_rules(
            user_id=user_id, evaluation_time=overnight_utc
        )
        assert quiet_eval.triggered_notifications == 1
        assert quiet_eval.suppressed_quiet_hours_deliveries == 2
        assert len(ConsoleEmailProvider.last_outbox) == 0

    # 5. Inspect GET /api/v1/notifications, mark read, and verify one-click opt-out
    notifs_res = await api_client.get("/api/v1/notifications")
    assert notifs_res.status_code == 200
    notifs = notifs_res.json()["data"]
    assert len(notifs) == 2
    latest_statuses = {d["status"] for d in notifs[0]["deliveries"]}
    assert latest_statuses == {"suppressed_quiet_hours"}

    mark_res = await api_client.patch(
        f"/api/v1/notifications/{notifs[0]['id']}/read",
        headers=_csrf(api_client),
    )
    assert mark_res.status_code == 200
    assert mark_res.json()["data"]["read_at"] is not None

    opt_out = await api_client.post(
        "/api/v1/alerts/unsubscribe-all", headers=_csrf(api_client)
    )
    assert opt_out.status_code == 200
    assert opt_out.json()["data"]["disabled_rules_count"] == 2

    # 6. Cron endpoint enforces bearer secret & cross-user IDOR returns 404
    cron_ok = await api_client.get(
        "/api/v1/system/cron/evaluate-alerts",
        headers={"Authorization": "Bearer test-cron-secret-value-123456"},
    )
    assert cron_ok.status_code == 200

    api_client.cookies.clear()
    await _register(api_client, "other-resident@example.com")
    assert (
        await api_client.patch(
            f"/api/v1/alerts/{rule_id}",
            headers=_csrf(api_client),
            json={"is_enabled": True},
        )
    ).status_code == 404
    assert (
        await api_client.patch(
            f"/api/v1/notifications/{notifs[0]['id']}/read",
            headers=_csrf(api_client),
        )
    ).status_code == 404


async def test_community_privacy_consent_moderation_ai_tool_and_account_anonymization(
    api_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    # 1. Regular user cannot create communities or view moderation queue
    member_a_id = await _register(api_client, "private-member@example.com", "Secret Resident A")
    forbidden_create = await api_client.post(
        "/api/v1/communities",
        headers=_csrf(api_client),
        json={
            "slug": "unauthorized-circle",
            "name": "Unauthorized Circle",
            "city": "Bengaluru",
            "coarse_boundary_label": "East Bengaluru",
            "description": "Should require moderator or admin role.",
        },
    )
    assert forbidden_create.status_code == 403
    assert (await api_client.get("/api/v1/admin/community/reports")).status_code == 403
    member_a_session = api_client.cookies.get("airwise_session", "")
    member_a_csrf = api_client.cookies.get("airwise_csrf", "")

    # 2. Register Moderator user and promote role in DB
    api_client.cookies.clear()
    mod_id = await _register(api_client, "moderator@example.com", "Neighborhood Moderator")
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        await session.execute(
            update(User).where(User.id == mod_id).values(role="moderator")
        )
        await session.commit()

    comm_res = await api_client.post(
        "/api/v1/communities",
        headers=_csrf(api_client),
        json={
            "slug": "indiranagar-clean-commute",
            "name": "Indiranagar Clean Commute",
            "city": "Bengaluru",
            "coarse_boundary_label": "East Bengaluru · Metro Corridor",
            "description": "Voluntary neighborhood transit and school no-idling initiatives.",
        },
    )
    assert comm_res.status_code == 201
    comm_id = comm_res.json()["data"]["id"]

    now = datetime.now(tz=UTC)
    init_res = await api_client.post(
        f"/api/v1/communities/{comm_id}/initiatives",
        headers=_csrf(api_client),
        json={
            "title": "No-Idling School Gate Week",
            "description": "Switch off engines during school drop-off & pick-up waits.",
            "challenge_type": "no_idling_school_week",
            "starts_at": (now - timedelta(days=1)).isoformat(),
            "ends_at": (now + timedelta(days=7)).isoformat(),
        },
    )
    assert init_res.status_code == 201
    init_id = init_res.json()["data"]["id"]
    mod_session = api_client.cookies.get("airwise_session", "")
    mod_csrf = api_client.cookies.get("airwise_csrf", "")

    # 3. Member A joins WITHOUT public display consent (default False) & logs action
    api_client.cookies.set("airwise_session", member_a_session)
    api_client.cookies.set("airwise_csrf", member_a_csrf)
    join_a = await api_client.post(
        f"/api/v1/communities/{comm_id}/join",
        headers={"X-CSRF-Token": member_a_csrf, "Origin": "http://localhost:3000"},
        json={"public_display_consent": False},
    )
    assert join_a.status_code == 200

    part_a = await api_client.post(
        f"/api/v1/communities/{comm_id}/initiatives/{init_id}/participate",
        headers={"X-CSRF-Token": member_a_csrf, "Origin": "http://localhost:3000"},
        json={"self_reported_actions_count": 2, "commute_distance_saved_km": 10.0},
    )
    assert part_a.status_code == 201
    assert part_a.json()["data"]["estimated_avoided_co2e_kg"] == 1.4

    # 4. Member B joins WITH explicit public_display_consent=True & logs action
    api_client.cookies.clear()
    await _register(api_client, "optin-member@example.com", "OptIn Resident B")
    await api_client.post(
        f"/api/v1/communities/{comm_id}/join",
        headers=_csrf(api_client),
        json={"public_display_consent": True},
    )
    await api_client.post(
        f"/api/v1/communities/{comm_id}/initiatives/{init_id}/participate",
        headers=_csrf(api_client),
        json={"self_reported_actions_count": 3, "commute_distance_saved_km": 10.0},
    )
    member_b_session = api_client.cookies.get("airwise_session", "")
    member_b_csrf = api_client.cookies.get("airwise_csrf", "")

    # 5. Guest views public community dashboard -> sees OptIn Resident B ONLY, zero unconsented PII!
    api_client.cookies.clear()
    guest_detail = await api_client.get(f"/api/v1/communities/{comm_id}")
    assert guest_detail.status_code == 200
    detail_body = guest_detail.json()["data"]
    assert detail_body["total_self_reported_actions"] == 5
    assert detail_body["total_estimated_avoided_co2e_kg"] == 2.8
    assert detail_body["consented_member_display_names"] == ["OptIn Resident B"]
    assert "Secret Resident A" not in str(detail_body)
    assert "example.com" not in str(detail_body)

    # 6. Verify 12th allowlisted AI tool (get_community_initiatives) returns live active challenge
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        executor = ToolExecutor(
            session=session,
            settings=Settings(app_env="test"),
            user_id=member_a_id,
            request=ChatRequest(
                message="What clean air challenges exist in Bengaluru?",
                city="Bengaluru",
                standard=AQIStandard.INDIA_NAQI,
                ai_consent=True,
            ),
            knowledge=KnowledgeService(session, _StubGateway(), "gemini-embedding-001"),
        )
        comm_tool_res = await executor.execute(ToolCall(name="get_community_initiatives"))
        assert comm_tool_res["status"] == "available"
        inits_list = comm_tool_res["initiatives"]
        assert isinstance(inits_list, list) and len(inits_list) == 1
        assert inits_list[0]["title"] == "No-Idling School Gate Week"

    # 7. Member B exports data & deletes account -> membership deleted, aggregate anonymized!
    api_client.cookies.set("airwise_session", member_b_session)
    api_client.cookies.set("airwise_csrf", member_b_csrf)
    b_headers = {"X-CSRF-Token": member_b_csrf, "Origin": "http://localhost:3000"}
    await api_client.post(
        "/api/v1/alerts",
        headers=b_headers,
        json={
            "city": "Bengaluru",
            "alert_type": "clean_air_window",
            "aqi_standard": "india_naqi",
            "threshold_value": 100,
        },
    )
    export_b = (await api_client.get("/api/v1/users/me/export")).json()["data"]
    assert len(export_b["community_memberships"]) == 1
    assert len(export_b["alert_rules"]) == 1

    del_b = await api_client.delete("/api/v1/users/me", headers=b_headers)
    assert del_b.status_code == 200

    # Aggregate avoided CO2e (2.8 kg) remains intact while OptIn Resident B's name/ID are gone!
    api_client.cookies.clear()
    after_erasure = (await api_client.get(f"/api/v1/communities/{comm_id}")).json()["data"]
    assert after_erasure["total_estimated_avoided_co2e_kg"] == 2.8
    assert after_erasure["consented_member_display_names"] == []

    # 8. Member A reports an issue -> Moderator resolves by hiding initiative + records audit_log
    api_client.cookies.set("airwise_session", member_a_session)
    api_client.cookies.set("airwise_csrf", member_a_csrf)
    rep_res = await api_client.post(
        f"/api/v1/communities/{comm_id}/reports",
        headers={"X-CSRF-Token": member_a_csrf, "Origin": "http://localhost:3000"},
        json={
            "initiative_id": init_id,
            "reason_category": "misinformation",
            "details": "Needs updated school timing details.",
        },
    )
    assert rep_res.status_code == 201
    report_id = rep_res.json()["data"]["id"]

    api_client.cookies.set("airwise_session", mod_session)
    api_client.cookies.set("airwise_csrf", mod_csrf)
    mod_headers = {"X-CSRF-Token": mod_csrf, "Origin": "http://localhost:3000"}
    queue = (await api_client.get("/api/v1/admin/community/reports?status=open")).json()["data"]
    assert len(queue) == 1

    resolve_res = await api_client.patch(
        f"/api/v1/admin/community/reports/{report_id}",
        headers=mod_headers,
        json={
            "action": "hide_initiative",
            "resolution_note": "Hidden pending organizer update.",
        },
    )
    assert resolve_res.status_code == 200
    assert resolve_res.json()["data"]["status"] == "resolved_removed"

    public_inits_after = (
        await api_client.get(f"/api/v1/communities/{comm_id}/initiatives")
    ).json()["data"]
    assert public_inits_after == []

    async with AsyncSession(db_engine) as session:
        audit_actions = set(await session.scalars(select(AuditLog.action)))
        assert {
            "community.created",
            "community.initiative_created",
            "community.report_resolved",
        }.issubset(audit_actions)
        anon_count = await session.scalar(
            select(func.count())
            .select_from(CommunityParticipation)
            .where(CommunityParticipation.user_id.is_(None))
        )
        assert anon_count == 1
        assert await session.scalar(select(func.count()).select_from(AlertRule)) == 0
        assert await session.scalar(select(func.count()).select_from(Notification)) == 0
        assert await session.scalar(select(func.count()).select_from(CommunityMember)) == 2
