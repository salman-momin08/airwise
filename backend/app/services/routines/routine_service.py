"""Daily smog-safe routine planner service with explicit confirmation gates."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ExternalProviderUnavailableError, ResourceNotFoundError
from app.models.planning import DailyRoutine, ImpactEstimate
from app.repositories.identity_repository import IdentityRepository
from app.repositories.planning_repository import PlanningRepository
from app.schemas.air_quality import AirQualityForecastSchema, CurrentAirQualitySchema
from app.schemas.impact import TransportImpactRequest
from app.schemas.routines import (
    ConfidenceLiteral,
    DailyRoutineSchema,
    EnvironmentalSnapshotSummarySchema,
    EnvironmentTypeLiteral,
    GenerateRoutineRequest,
    RoutineActivitySchema,
    RoutineComparisonSchema,
    RoutineStatusLiteral,
    TimeBlockLiteral,
    UpdateRoutineRequest,
)
from app.schemas.weather import CurrentWeatherSchema
from app.services.air_quality.aqi_calculator import AQIStandard
from app.services.air_quality.telemetry_service import AirQualityTelemetryService
from app.services.impact.calculators import estimate_relative_exposure_change
from app.services.impact.impact_service import ImpactEngineService, serialize_impact_record
from app.services.recommendations.safety_engine import (
    EnvironmentalRuleContext,
    evaluate_environmental_rules,
)
from app.services.routines.slot_builder import (
    build_default_routine_slots,
    build_edited_routine_slots,
    build_window_comparison_options,
    parse_hhmm,
)
from app.services.weather.weather_service import WeatherTelemetryService


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class RoutinePlannerService:
    """Service managing smog-aware Morning–Night daily routines with explicit user confirmation."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._repo = PlanningRepository(session)
        self._identity_repo = IdentityRepository(session)
        self._impact_service = ImpactEngineService(session, settings)

    async def _fetch_environmental_bundle(
        self, *, city: str, standard: AQIStandard
    ) -> tuple[
        CurrentAirQualitySchema | None,
        AirQualityForecastSchema | None,
        CurrentWeatherSchema | None,
    ]:
        aq_service = AirQualityTelemetryService(self._session, self._settings)
        weather_service = WeatherTelemetryService(self._session, self._settings)
        try:
            current = await aq_service.get_current_air_quality(city=city, standard=standard)
        except ExternalProviderUnavailableError:
            current = None
        try:
            forecast = await aq_service.get_air_quality_forecast(
                city=city, standard=standard, hours=24
            )
        except ExternalProviderUnavailableError:
            forecast = None
        try:
            weather = await weather_service.get_current_weather(city=city)
        except ExternalProviderUnavailableError:
            weather = None
        return current, forecast, weather

    async def _serialize_routine(self, routine: DailyRoutine) -> DailyRoutineSchema:
        est_ids = {
            act.impact_estimate_id
            for act in routine.activities
            if act.impact_estimate_id is not None
        }
        estimates_by_id: dict[
            uuid.UUID, ImpactEstimate
        ] = await self._repo.get_impact_estimates_by_ids(est_ids)
        std = (
            AQIStandard.US_EPA
            if routine.aqi_standard == AQIStandard.US_EPA.value
            else AQIStandard.INDIA_NAQI
        )
        env_summary = (
            EnvironmentalSnapshotSummarySchema.model_validate(routine.environmental_summary)
            if routine.environmental_summary is not None
            else None
        )
        activity_items: list[RoutineActivitySchema] = []
        for act in sorted(routine.activities, key=lambda item: item.slot_order):
            est_record = (
                estimates_by_id.get(act.impact_estimate_id)
                if act.impact_estimate_id is not None
                else None
            )
            activity_items.append(
                RoutineActivitySchema(
                    id=act.id,
                    slot_order=act.slot_order,
                    time_block=cast(TimeBlockLiteral, act.time_block),
                    start_time=act.start_time.strftime("%H:%M"),
                    duration_minutes=act.duration_minutes,
                    title=act.title,
                    environment_type=cast(EnvironmentTypeLiteral, act.environment_type),
                    exposure_note=act.exposure_note,
                    safer_alternative=act.safer_alternative,
                    explanation=act.explanation,
                    safety_warning=act.safety_warning,
                    impact_estimate=(
                        serialize_impact_record(est_record) if est_record is not None else None
                    ),
                    confidence=cast(ConfidenceLiteral, act.confidence),
                )
            )

        status_literal = (
            cast(RoutineStatusLiteral, routine.status)
            if routine.status in {"draft", "confirmed", "archived"}
            else "draft"
        )
        return DailyRoutineSchema(
            id=routine.id,
            location_id=routine.location_id,
            city=routine.city,
            plan_date=routine.plan_date,
            aqi_standard=std,
            status=status_literal,
            environmental_snapshot_at=(
                _ensure_utc(routine.environmental_snapshot_at)
                if routine.environmental_snapshot_at is not None
                else None
            ),
            environmental_summary=env_summary,
            activities=activity_items,
            requires_explicit_confirmation=status_literal == "draft",
            created_at=_ensure_utc(routine.created_at),
            updated_at=_ensure_utc(routine.updated_at),
        )

    async def generate_draft_routine(
        self,
        *,
        user_id: uuid.UUID,
        payload: GenerateRoutineRequest,
    ) -> DailyRoutineSchema:
        city = payload.city
        if payload.location_id is not None:
            saved_loc = await self._identity_repo.get_saved_location_for_user(
                user_id=user_id, location_id=payload.location_id
            )
            if saved_loc is None:
                raise ResourceNotFoundError("Saved location was not found.")
            city = saved_loc.city

        user = await self._identity_repo.get_user_by_id(user_id)
        prefs = user.preferences if user is not None else None
        consented = prefs is not None and prefs.consent_updated_at is not None

        current, forecast, weather = await self._fetch_environmental_bundle(
            city=city, standard=payload.standard
        )
        rules: EnvironmentalRuleContext = evaluate_environmental_rules(
            standard=payload.standard,
            current=current,
            weather=weather,
            forecast=forecast,
            has_vulnerable_member=(
                bool(prefs.has_vulnerable_members) if consented and prefs else False
            ),
            age_category=prefs.age_category if consented and prefs else None,
            has_hepa_purifier=bool(prefs.has_hepa_purifier) if consented and prefs else False,
            budget_tier=prefs.budget_tier if consented and prefs else None,
            cooking_type=prefs.cooking_type if consented and prefs else None,
        )

        work_start = parse_hhmm(
            str(prefs.work_schedule.get("start_time", "09:00"))
            if consented and prefs and isinstance(prefs.work_schedule, dict)
            else "09:00",
            time(9, 0),
        )
        school_note = (
            " Includes conservative child school-run protection "
            "(well-fitted mask + enclosed transit)."
            if consented and prefs and (prefs.school_schedule or prefs.has_vulnerable_members)
            else ""
        )

        commute_est_id: uuid.UUID | None = None
        if payload.commute_distance_km > 0:
            calc_res, _ = await self._impact_service.calculate(
                TransportImpactRequest(
                    distance_km=payload.commute_distance_km,
                    baseline_mode="car_solo_petrol",
                    alternative_mode="metro_rail",
                    city=city,
                    standard=payload.standard,
                )
            )
            est_rec = await self._impact_service.persist_impact_result(
                user_id=user_id,
                user_action_id=None,
                result=calc_res,
            )
            commute_est_id = est_rec.id

        exposure_est_id: uuid.UUID | None = None
        if rules.pm25_ug_m3 is not None and rules.block_outdoor_exertion:
            exp_res = estimate_relative_exposure_change(
                outdoor_pm25_ug_m3=rules.pm25_ug_m3,
                duration_hours=0.75,
                baseline_env_modifier=1.0,
                alternative_env_modifier=0.35 if rules.has_hepa_purifier else 0.55,
                assumption_note=(
                    "Shifting 45-minute workout from unfiltered outdoor air to indoor space"
                ),
            )
            exp_rec = await self._impact_service.persist_impact_result(
                user_id=user_id,
                user_action_id=None,
                result=exp_res,
            )
            exposure_est_id = exp_rec.id

        now = datetime.now(tz=UTC)
        summary = EnvironmentalSnapshotSummarySchema(
            city=current.city if current is not None else city,
            standard=payload.standard,
            status="available" if rules.is_available else "unavailable",
            aqi=rules.aqi,
            category=rules.category,
            pm25_ug_m3=rules.pm25_ug_m3,
            provider=current.provider if current is not None else "unavailable",
            source_type=current.source_type if current is not None else "unavailable",
            measured_at=current.measured_at if current is not None else None,
            is_stale=rules.is_stale,
            is_development_fixture=rules.is_development_fixture,
            inversion_risk_flag=rules.inversion_risk,
            dispersion_note=weather.dispersion_note if weather is not None else None,
            ventilation_guidance=rules.ventilation_guidance,
        )

        routine = DailyRoutine(
            id=uuid.uuid4(),
            user_id=user_id,
            location_id=payload.location_id,
            city=summary.city,
            plan_date=payload.plan_date or now.date(),
            aqi_standard=payload.standard.value,
            status="draft",
            environmental_snapshot_at=current.measured_at if current is not None else now,
            environmental_summary=summary.model_dump(mode="json"),
            created_at=now,
            updated_at=now,
        )
        self._session.add(routine)
        await self._session.flush()

        slots = build_default_routine_slots(
            routine_id=routine.id,
            rules=rules,
            work_start=work_start,
            school_note=school_note,
            exposure_est_id=exposure_est_id,
            commute_est_id=commute_est_id,
        )
        self._session.add_all(slots)
        await self._session.commit()

        reloaded = await self._repo.require_routine(user_id=user_id, routine_id=routine.id)
        return await self._serialize_routine(reloaded)

    async def list_routines(self, *, user_id: uuid.UUID) -> list[DailyRoutineSchema]:
        """List all saved daily routines belonging to `user_id`."""
        routines = await self._repo.list_routines(user_id=user_id)
        return [await self._serialize_routine(item) for item in routines]

    async def get_routine(self, *, user_id: uuid.UUID, routine_id: uuid.UUID) -> DailyRoutineSchema:
        """Fetch a single user-owned daily routine by ID."""
        routine = await self._repo.require_routine(user_id=user_id, routine_id=routine_id)
        return await self._serialize_routine(routine)

    async def update_routine(
        self,
        *,
        user_id: uuid.UUID,
        routine_id: uuid.UUID,
        payload: UpdateRoutineRequest,
    ) -> DailyRoutineSchema:
        """Update routine activity slots or explicit confirmation status."""
        routine = await self._repo.require_routine(user_id=user_id, routine_id=routine_id)
        std = (
            AQIStandard.US_EPA
            if routine.aqi_standard == AQIStandard.US_EPA.value
            else AQIStandard.INDIA_NAQI
        )
        snap_aqi: int | None = None
        if isinstance(routine.environmental_summary, dict):
            raw_aqi = routine.environmental_summary.get("aqi")
            if isinstance(raw_aqi, int):
                snap_aqi = raw_aqi

        if payload.activities is not None:
            replacement = build_edited_routine_slots(
                routine_id=routine.id,
                standard=std,
                snap_aqi=snap_aqi,
                slots=payload.activities,
            )
            await self._repo.replace_routine_activities(routine=routine, activities=replacement)

        if payload.status is not None:
            routine.status = payload.status
            routine.updated_at = datetime.now(tz=UTC)

        await self._session.commit()
        reloaded = await self._repo.require_routine(user_id=user_id, routine_id=routine_id)
        return await self._serialize_routine(reloaded)

    async def delete_routine(self, *, user_id: uuid.UUID, routine_id: uuid.UUID) -> None:
        """Delete a user-owned daily routine."""
        await self._repo.delete_routine(user_id=user_id, routine_id=routine_id)
        await self._session.commit()

    async def compare_routine_windows(
        self,
        *,
        city: str,
        standard: AQIStandard,
        has_vulnerable_member: bool = False,
    ) -> RoutineComparisonSchema:
        """Compare Morning–Night windows against verified AQI, forecast, and inversion risk."""
        current, forecast, weather = await self._fetch_environmental_bundle(
            city=city, standard=standard
        )
        rules = evaluate_environmental_rules(
            standard=standard,
            current=current,
            weather=weather,
            forecast=forecast,
            has_vulnerable_member=has_vulnerable_member,
        )
        windows = build_window_comparison_options(
            standard=standard,
            rules=rules,
            forecast=forecast,
        )

        return RoutineComparisonSchema(
            city=current.city if current is not None else city,
            standard=standard,
            current_aqi=rules.aqi,
            is_stale=rules.is_stale,
            is_development_fixture=rules.is_development_fixture,
            priority_hierarchy_note=(
                "1. Exposure Safety -> 2. User Schedule Constraints -> 3. Feasibility -> "
                "4. Emission Reduction -> 5. Cost -> 6. Convenience"
            ),
            windows=windows,
        )


__all__ = ["RoutinePlannerService", "date"]
