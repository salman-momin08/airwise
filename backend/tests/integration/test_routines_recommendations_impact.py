from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.ai.gateway.gemini import OutputModel
from app.ai.rag.knowledge import DocumentInput, KnowledgeService
from app.ai.tools.executor import ToolExecutor
from app.core.config import Settings
from app.models.planning import (
    DailyRoutine,
    ImpactEstimate,
    Recommendation,
    RecommendationFeedback,
    RoutineActivity,
    UserAction,
)
from app.schemas.assistant import ChatRequest, ToolCall
from app.schemas.recommendations import GenerateRecommendationsRequest
from app.services.air_quality.aqi_calculator import AQIStandard
from app.services.recommendations.recommendation_service import HybridRecommendationService

def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {
        "X-CSRF-Token": client.cookies.get("airwise_csrf", ""),
        "Origin": "http://localhost:3000",
    }

async def _register_user(client: AsyncClient, email: str) -> str:
    res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Phase5SecurePassword2026",
            "display_name": "Phase5 User",
            "preferred_aqi_standard": "india_naqi",
        },
    )
    assert res.status_code == 201
    return str(res.json()["data"]["user_id"])

class _NumericAttemptGateway:
    """Stub gateway verifying LLM cannot alter deterministic impact numbers."""

    model_name = "gemini-stub"
    token_usage = 15

    def __init__(self, *, inject_numbers: bool) -> None:
        self._inject_numbers = inject_numbers

    async def generate(
        self, *, system: str, prompt: str, schema: type[OutputModel]
    ) -> OutputModel:
        reason = (
            "Switching cuts 999 kg of carbon immediately!"
            if self._inject_numbers
            else "Shifting passenger trips to shared rail cuts tailpipe exhaust cleanly."
        )
        return schema.model_validate(
            {
                "cards": [
                    {"category": "transport", "reason": reason},
                ]
            }
        )

    async def embed(
        self, text: str, *, task: Literal["RETRIEVAL_QUERY", "RETRIEVAL_DOCUMENT"]
    ) -> list[float]:
        return [1.0] + [0.0] * 767

async def test_exposure_safety_overrides_transport_emissions_in_severe_smog(
    api_client: AsyncClient,
) -> None:
    # Guest access works on /impact/factors and /impact/calculate
    factors_res = await api_client.get("/api/v1/impact/factors?category=transport")
    assert factors_res.status_code == 200
    codes = {item["mode_or_region_code"] for item in factors_res.json()["data"]}
    assert {"car_solo_petrol", "metro_rail", "bicycle", "walk"}.issubset(codes)

    # Severe smog in Delhi fixture: cycling saves CO2e numerically, but exposure safety blocks it
    delhi_cycle = await api_client.post(
        "/api/v1/impact/calculate",
        json={
            "calculator_type": "transport",
            "city": "Delhi",
            "standard": "india_naqi",
            "distance_km": 10.0,
            "baseline_mode": "car_solo_petrol",
            "alternative_mode": "bicycle",
        },
    )
    assert delhi_cycle.status_code == 200
    cycle_data = delhi_cycle.json()["data"]
    assert cycle_data["is_estimate"] is True
    assert cycle_data["estimated_difference"] == 1.68
    assert cycle_data["exposure_screening"]["recommended_for_current_aqi"] is False
    assert "Exposure-First Safety Override" in cycle_data["exposure_screening"]["exposure_warning"]
    assert "Metro" in cycle_data["exposure_screening"]["safer_commute_fallback"]

    # Enclosed metro rail in Delhi is exposure-safe AND lowers CO2e
    delhi_metro = await api_client.post(
        "/api/v1/impact/calculate",
        json={
            "calculator_type": "transport",
            "city": "Delhi",
            "standard": "india_naqi",
            "distance_km": 10.0,
            "baseline_mode": "car_solo_petrol",
            "alternative_mode": "metro_rail",
        },
    )
    assert delhi_metro.status_code == 200
    assert delhi_metro.json()["data"]["exposure_screening"]["recommended_for_current_aqi"] is True
    assert delhi_metro.json()["data"]["estimated_difference"] == 1.4

    # Clean/satisfactory air in Bengaluru allows active cycling
    blr_cycle = await api_client.post(
        "/api/v1/impact/calculate",
        json={
            "calculator_type": "transport",
            "city": "Bengaluru",
            "standard": "india_naqi",
            "distance_km": 10.0,
            "baseline_mode": "car_solo_petrol",
            "alternative_mode": "bicycle",
        },
    )
    assert blr_cycle.status_code == 200
    assert blr_cycle.json()["data"]["exposure_screening"]["recommended_for_current_aqi"] is True

async def test_routine_planner_requires_explicit_confirmation_and_flags_unsafe_edits(
    api_client: AsyncClient,
) -> None:
    await _register_user(api_client, "planner@example.com")

    # Missing CSRF is rejected
    no_csrf = await api_client.post(
        "/api/v1/routines/generate",
        json={"city": "Delhi", "standard": "india_naqi", "commute_distance_km": 12},
    )
    assert no_csrf.status_code == 403

    # Generate routine in severe-smog Delhi -> starts strictly as unconfirmed draft
    gen_res = await api_client.post(
        "/api/v1/routines/generate",
        headers=_csrf_headers(api_client),
        json={"city": "Delhi", "standard": "india_naqi", "commute_distance_km": 12},
    )
    assert gen_res.status_code == 201
    routine = gen_res.json()["data"]
    routine_id = routine["id"]
    assert routine["status"] == "draft"
    assert routine["requires_explicit_confirmation"] is True
    assert len(routine["activities"]) == 5
    # Morning slot in severe smog is shifted indoors automatically
    assert routine["activities"][0]["time_block"] == "morning"
    assert routine["activities"][0]["environment_type"] == "indoor"

    # Edit morning slot to outdoor WITHOUT confirming -> stays draft and attaches safety_warning
    edited_slots = [
        {
            "time_block": slot["time_block"],
            "start_time": slot["start_time"],
            "duration_minutes": slot["duration_minutes"],
            "title": "Outdoor Marathon Run" if idx == 0 else slot["title"],
            "environment_type": "outdoor" if idx == 0 else slot["environment_type"],
        }
        for idx, slot in enumerate(routine["activities"])
    ]
    patch_edit = await api_client.patch(
        f"/api/v1/routines/{routine_id}",
        headers=_csrf_headers(api_client),
        json={"activities": edited_slots},
    )
    assert patch_edit.status_code == 200
    edited_data = patch_edit.json()["data"]
    assert edited_data["status"] == "draft"
    assert edited_data["requires_explicit_confirmation"] is True
    assert "Exposure Warning" in (edited_data["activities"][0]["safety_warning"] or "")

    # Explicit confirmation transitions routine to confirmed
    confirm_res = await api_client.patch(
        f"/api/v1/routines/{routine_id}",
        headers=_csrf_headers(api_client),
        json={"status": "confirmed"},
    )
    assert confirm_res.status_code == 200
    assert confirm_res.json()["data"]["status"] == "confirmed"
    assert confirm_res.json()["data"]["requires_explicit_confirmation"] is False

    # Cross-user IDOR check -> returns 404
    api_client.cookies.clear()
    await _register_user(api_client, "intruder@example.com")
    assert (await api_client.get(f"/api/v1/routines/{routine_id}")).status_code == 404
    assert (
        await api_client.patch(
            f"/api/v1/routines/{routine_id}",
            headers=_csrf_headers(api_client),
            json={"status": "archived"},
        )
    ).status_code == 404

async def test_hybrid_recommendations_enforce_immutable_numbers_and_all_five_categories(
    api_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    user_id_str = await _register_user(api_client, "recs@example.com")
    import uuid

    user_uuid = uuid.UUID(user_id_str)

    # Seed a verified KnowledgeDocument so citation linking resolves to real DB records
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        knowledge = KnowledgeService(
            session, _NumericAttemptGateway(inject_numbers=False), "gemini-embedding-001"
        )
        doc_id = await knowledge.ingest(
            DocumentInput(
                title="EPA Home Air Cleaners Summary",
                publisher="US EPA",
                source_url="https://www.epa.gov/indoor-air-quality-iaq/guide-air-cleaners-home",
                jurisdiction="US",
                last_reviewed_date=datetime.now(UTC),
                content=(
                    "Source control and room-sized HEPA filtration "
                    "reduce indoor particulate exposure."
                ),
            )
        )

    # 1. Generate via HTTP in severe-smog Delhi -> all 5 categories + deterministic override
    gen_res = await api_client.post(
        "/api/v1/recommendations/generate",
        headers=_csrf_headers(api_client),
        json={"city": "Delhi", "standard": "india_naqi", "commute_distance_km": 10},
    )
    assert gen_res.status_code == 200
    cards = gen_res.json()["data"]
    assert {c["category"] for c in cards} == {
        "routine",
        "transport",
        "indoor_air",
        "household_sustainability",
        "community",
    }
    transport_card = next(c for c in cards if c["category"] == "transport")
    assert transport_card["priority"] == "critical"
    assert transport_card["impact_estimate"]["estimated_difference"] == 1.4
    assert str(doc_id) in {ref["document_id"] for ref in transport_card["evidence_references"]}

    # Feedback persists and reflects on GET /recommendations/today
    fb_res = await api_client.post(
        f"/api/v1/recommendations/{transport_card['id']}/feedback",
        headers=_csrf_headers(api_client),
        json={"status": "completed", "note": "Took metro rail today"},
    )
    assert fb_res.status_code == 200
    today_cards = (await api_client.get("/api/v1/recommendations/today")).json()["data"]
    updated_tx = next(c for c in today_cards if c["id"] == transport_card["id"])
    assert updated_tx["latest_feedback"] == "completed"

    # 2. Verify LLM numerical injection is rejected and deterministic impact math stays untouched
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        bad_ai_service = HybridRecommendationService(
            session,
            Settings(app_env="test"),
            gateway=_NumericAttemptGateway(inject_numbers=True),
        )
        bad_cards = await bad_ai_service.generate_recommendations(
            user_id=user_uuid,
            payload=GenerateRecommendationsRequest(
                city="Bengaluru",
                standard=AQIStandard.INDIA_NAQI,
                commute_distance_km=10.0,
                use_ai_phrasing=True,
                ai_consent=True,
            ),
        )
        tx_bad = next(c for c in bad_cards if c.category == "transport")
        assert tx_bad.is_ai_enriched is False
        assert "999" not in tx_bad.reason
        assert tx_bad.impact_estimate is not None
        assert tx_bad.impact_estimate.estimated_difference == 1.4

        good_ai_service = HybridRecommendationService(
            session,
            Settings(app_env="test"),
            gateway=_NumericAttemptGateway(inject_numbers=False),
        )
        good_cards = await good_ai_service.generate_recommendations(
            user_id=user_uuid,
            payload=GenerateRecommendationsRequest(
                city="Bengaluru",
                standard=AQIStandard.INDIA_NAQI,
                commute_distance_km=10.0,
                use_ai_phrasing=True,
                ai_consent=True,
            ),
        )
        tx_good = next(c for c in good_cards if c.category == "transport")
        assert tx_good.is_ai_enriched is True
        assert tx_good.impact_estimate is not None
        assert tx_good.impact_estimate.estimated_difference == 1.4

async def test_action_logging_summary_ai_tools_export_and_erasure(
    api_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    user_id_str = await _register_user(api_client, "impact-owner@example.com")
    import uuid

    user_uuid = uuid.UUID(user_id_str)

    # Log a transport action and an appliance energy action
    act1 = await api_client.post(
        "/api/v1/impact/actions",
        headers=_csrf_headers(api_client),
        json={
            "action_type": "public_transit_trip",
            "title": "Used metro rail instead of solo petrol car",
            "quantity": 15,
            "unit": "km",
            "calculation": {
                "calculator_type": "transport",
                "distance_km": 15,
                "baseline_mode": "car_solo_petrol",
                "alternative_mode": "metro_rail",
                "city": "Bengaluru",
                "standard": "india_naqi",
            },
        },
    )
    assert act1.status_code == 201
    assert act1.json()["data"]["is_self_reported"] is True

    act2 = await api_client.post(
        "/api/v1/impact/actions",
        headers=_csrf_headers(api_client),
        json={
            "action_type": "appliance_load_reduction",
            "title": "Trimmed HVAC wattage for 4 hours",
            "quantity": 4,
            "unit": "hours",
            "calculation": {
                "calculator_type": "household_energy",
                "baseline_power_kw": 2.0,
                "alternative_power_kw": 1.0,
                "operating_hours": 4.0,
                "grid_region_code": "india_cea_grid_avg",
            },
        },
    )
    assert act2.status_code == 201

    summary = (await api_client.get("/api/v1/impact/summary")).json()["data"]
    assert summary["total_logged_actions"] == 2
    assert summary["transport_avoided_co2e_kg"] == 2.1
    assert summary["energy_avoided_co2e_kg"] == 2.864
    assert summary["estimated_avoided_co2e_kg"] == 4.964

    history = (await api_client.get("/api/v1/impact/history")).json()["data"]
    assert len(history) == 2

    # Verify Phase 5 AI tools (compare_daily_routines & generate_sustainable_alternatives)
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        executor = ToolExecutor(
            session=session,
            settings=Settings(app_env="test"),
            user_id=user_uuid,
            request=ChatRequest(
                message="Compare my daily slots and commute alternatives",
                city="Delhi",
                standard=AQIStandard.INDIA_NAQI,
                ai_consent=True,
            ),
            knowledge=KnowledgeService(
                session, _NumericAttemptGateway(inject_numbers=False), "gemini-embedding-001"
            ),
        )
        routine_tool_res = await executor.execute(ToolCall(name="compare_daily_routines"))
        assert routine_tool_res["status"] == "available"
        alts_tool_res = await executor.execute(ToolCall(name="generate_sustainable_alternatives"))
        assert alts_tool_res["status"] == "available"
        alts_list = alts_tool_res["alternatives"]
        assert isinstance(alts_list, list)
        bike_opt = next(item for item in alts_list if item["option_code"] == "bicycle")
        assert bike_opt["exposure_safe_now"] is False

    # Export includes Phase 5 logged actions, and account deletion erases all Phase 5 rows cleanly
    exported = (await api_client.get("/api/v1/users/me/export")).json()["data"]
    assert len(exported["logged_actions"]) == 2

    del_res = await api_client.delete("/api/v1/users/me", headers=_csrf_headers(api_client))
    assert del_res.status_code == 200

    async with AsyncSession(db_engine) as session:
        for model in (
            UserAction,
            ImpactEstimate,
            DailyRoutine,
            RoutineActivity,
            Recommendation,
            RecommendationFeedback,
        ):
            assert await session.scalar(select(func.count()).select_from(model)) == 0
