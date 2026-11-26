from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ExternalProviderUnavailableError, ResourceNotFoundError
from app.models.planning import DailyRoutine, ImpactEstimate, RoutineActivity
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
    RoutineWindowOptionSchema,
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
from app.services.weather.weather_service import WeatherTelemetryService


def _parse_hhmm(value: str, fallback: time) -> time:
    try:
        parts = value.split(":")
        return time(hour=int(parts[0]), minute=int(parts[1]))
    except (ValueError, IndexError):
        return fallback


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
        estimates_by_id: dict[uuid.UUID, ImpactEstimate] = (
            await self._repo.get_impact_estimates_by_ids(est_ids)
        )
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

        work_start = _parse_hhmm(
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

        conf: ConfidenceLiteral = (
            "low" if (not rules.is_available or rules.is_stale) else "medium"
        )
        morning_outdoor_blocked = rules.block_outdoor_exertion or rules.inversion_risk
        slots: list[RoutineActivity] = [
            RoutineActivity(
                id=uuid.uuid4(),
                routine_id=routine.id,
                slot_order=0,
                time_block="morning",
                start_time=time(7, 0),
                duration_minutes=45,
                title=(
                    "Indoor Mobility & Stretching (Smog-Safe Morning Block)"
                    if morning_outdoor_blocked
                    else "Moderate Morning Walk Away from Arterial Roads"
                ),
                environment_type="indoor" if morning_outdoor_blocked else "outdoor",
                exposure_note=(
                    "Avoids early-morning boundary-layer smog & thermal inversion peak."
                    if morning_outdoor_blocked
                    else "Ambient AQI currently supports moderate outdoor movement."
                ),
                safer_alternative=(
                    "Keep exterior windows closed and run certified HEPA filtration if available."
                    if morning_outdoor_blocked
                    else "Move indoors immediately if local haze or smoke odor develops."
                ),
                explanation=(
                    "Priority 1 (Exposure Safety): Morning surface PM2.5 concentrates before solar "
                    "mixing; indoor exercise protects respiratory health."
                    if morning_outdoor_blocked
                    else "Verified outdoor air quality is within acceptable morning limits."
                ),
                impact_estimate_id=exposure_est_id,
                confidence=conf,
            ),
            RoutineActivity(
                id=uuid.uuid4(),
                routine_id=routine.id,
                slot_order=1,
                time_block="midday",
                start_time=work_start,
                duration_minutes=45,
                title=(
                    "Enclosed Metro / Public Transit Commute (N95/FFP2 Mask Outdoors)"
                    if rules.block_active_outdoor_commute
                    else "Low-Emission Public Transit or Shared Commute"
                ),
                environment_type="transit",
                exposure_note=(
                    "Prioritizes enclosed cabin protection over open roadside cycling or walking."
                    + school_note
                ),
                safer_alternative=(
                    "Work from home if schedule flexibility allows during severe pollution."
                ),
                explanation=(
                    "Exposure safety overrides active-commute CO2e optimization during elevated "
                    "particulate episodes while still cutting solo-car emissions."
                    if rules.block_active_outdoor_commute
                    else "Shared rail/bus transit lowers per-passenger CO2e vs solo driving."
                ),
                impact_estimate_id=commute_est_id,
                confidence=conf,
            ),
            RoutineActivity(
                id=uuid.uuid4(),
                routine_id=routine.id,
                slot_order=2,
                time_block="afternoon",
                start_time=time(14, 0),
                duration_minutes=20,
                title=(
                    "Sealed Indoor Air & Filtration Check (Skip Open-Window Ventilation)"
                    if rules.severity_tier in {"severe", "unavailable"}
                    else "Brief Mid-Afternoon Ventilation & Indoor Air Check"
                ),
                environment_type="indoor",
                exposure_note=rules.ventilation_guidance,
                safer_alternative="Use damp microfiber dusting instead of dry sweeping.",
                explanation=(
                    rules.cleaner_window_note
                    or (
                        "Afternoon solar mixing typically offers the lowest "
                        "relative outdoor stagnation."
                    )
                ),
                impact_estimate_id=None,
                confidence=conf,
            ),
            RoutineActivity(
                id=uuid.uuid4(),
                routine_id=routine.id,
                slot_order=3,
                time_block="evening",
                start_time=time(18, 0),
                duration_minutes=45,
                title="Evening Return Transit & Low-Smoke Kitchen Exhaust Routine",
                environment_type="indoor",
                exposure_note=(
                    "Close street-facing windows before evening traffic & cooling inversion onset; "
                    "run kitchen exhaust fan while cooking."
                ),
                safer_alternative=(
                    "Prefer induction/electric or covered simmering to limit indoor fumes."
                ),
                explanation=(
                    "Evening rush-hour emissions combine with cooling air "
                    "to trap surface pollutants."
                ),
                impact_estimate_id=None,
                confidence=conf,
            ),
            RoutineActivity(
                id=uuid.uuid4(),
                routine_id=routine.id,
                slot_order=4,
                time_block="night",
                start_time=time(21, 30),
                duration_minutes=60,
                title="Clean-Air Sleep Preparation & Quiet Indoor Recovery",
                environment_type="indoor",
                exposure_note=rules.indoor_filtration_guidance,
                safer_alternative=(
                    "Seal bedroom door/window gaps and avoid candles, coils, or incense overnight."
                ),
                explanation=(
                    "Overnight sleep represents ~7–8 hours of continuous breathing; clean bedroom "
                    "air substantially lowers cumulative 24-hour particulate exposure."
                ),
                impact_estimate_id=None,
                confidence=conf,
            ),
        ]
        self._session.add_all(slots)
        await self._session.commit()

        reloaded = await self._repo.require_routine(user_id=user_id, routine_id=routine.id)
        return await self._serialize_routine(reloaded)

    async def list_routines(self, *, user_id: uuid.UUID) -> list[DailyRoutineSchema]:
        routines = await self._repo.list_routines(user_id=user_id)
        return [await self._serialize_routine(item) for item in routines]

    async def get_routine(
        self, *, user_id: uuid.UUID, routine_id: uuid.UUID
    ) -> DailyRoutineSchema:
        routine = await self._repo.require_routine(user_id=user_id, routine_id=routine_id)
        return await self._serialize_routine(routine)

    async def update_routine(
        self,
        *,
        user_id: uuid.UUID,
        routine_id: uuid.UUID,
        payload: UpdateRoutineRequest,
    ) -> DailyRoutineSchema:
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

        severe_cutoff = 301 if std == AQIStandard.INDIA_NAQI else 201
        poor_cutoff = 201 if std == AQIStandard.INDIA_NAQI else 151
        elevated_pollution = snap_aqi is not None and snap_aqi >= poor_cutoff

        if payload.activities is not None:
            replacement: list[RoutineActivity] = []
            for idx, slot in enumerate(payload.activities):
                warning: str | None = None
                safer = slot.safer_alternative
                if slot.environment_type == "outdoor" and elevated_pollution:
                    severity_word = (
                        "Severe/Hazardous"
                        if snap_aqi is not None and snap_aqi >= severe_cutoff
                        else "Poor/Unhealthy"
                    )
                    warning = (
                        f"Exposure Warning: Edited slot is marked outdoor during {severity_word} "
                        f"pollution ({std.value}={snap_aqi}). Consider shifting indoors or wearing "
                        "a well-fitted N95/FFP2 respirator."
                    )
                    if not safer:
                        safer = "Substitute indoor activity or enclosed filtered transit."

                replacement.append(
                    RoutineActivity(
                        id=uuid.uuid4(),
                        routine_id=routine.id,
                        slot_order=idx,
                        time_block=slot.time_block,
                        start_time=_parse_hhmm(slot.start_time, time(8, 0)),
                        duration_minutes=slot.duration_minutes,
                        title=slot.title,
                        environment_type=slot.environment_type,
                        exposure_note=(
                            "User-customized activity slot screened against snapshot AQI."
                        ),
                        safer_alternative=safer,
                        explanation="Explicitly edited by user.",
                        safety_warning=warning,
                        impact_estimate_id=None,
                        confidence="medium" if snap_aqi is not None else "low",
                    )
                )
            await self._repo.replace_routine_activities(
                routine=routine, activities=replacement
            )

        if payload.status is not None:
            routine.status = payload.status
            routine.updated_at = datetime.now(tz=UTC)

        await self._session.commit()
        reloaded = await self._repo.require_routine(user_id=user_id, routine_id=routine.id)
        return await self._serialize_routine(reloaded)

    async def delete_routine(self, *, user_id: uuid.UUID, routine_id: uuid.UUID) -> None:
        await self._repo.delete_routine(user_id=user_id, routine_id=routine_id)
        await self._session.commit()

    async def compare_routine_windows(
        self,
        *,
        city: str,
        standard: AQIStandard,
        has_vulnerable_member: bool = False,
    ) -> RoutineComparisonSchema:
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
        blocks: tuple[tuple[TimeBlockLiteral, str], ...] = (
            ("morning", "06:30–09:30"),
            ("midday", "11:30–13:30"),
            ("afternoon", "14:00–16:30"),
            ("evening", "17:30–20:30"),
            ("night", "21:00–06:00"),
        )
        windows: list[RoutineWindowOptionSchema] = []
        for idx, (block, label) in enumerate(blocks):
            pt = (
                forecast.points[min(idx * 3, len(forecast.points) - 1)]
                if forecast is not None and forecast.points
                else None
            )
            slot_aqi = pt.aqi if pt is not None and pt.aqi is not None else rules.aqi
            slot_cat = pt.category if pt is not None and pt.category is not None else rules.category
            poor_cutoff = 201 if standard == AQIStandard.INDIA_NAQI else 151
            slot_blocked = (
                rules.block_outdoor_exertion
                or (slot_aqi is not None and slot_aqi >= poor_cutoff)
                or (block in {"morning", "night"} and rules.inversion_risk)
            )
            windows.append(
                RoutineWindowOptionSchema(
                    time_block=block,
                    window_label=label,
                    expected_aqi=slot_aqi,
                    expected_category=slot_cat,
                    outdoor_exertion_allowed=not slot_blocked and rules.is_available,
                    recommended_environment=(
                        "indoor"
                        if slot_blocked or not rules.is_available
                        else ("transit" if block == "evening" else "outdoor")
                    ),
                    rationale=(
                        "Elevated pollution or inversion risk: keep activities indoors."
                        if slot_blocked
                        else (
                            "Live AQI unavailable: stay conservative until verified readings load."
                            if not rules.is_available
                            else "Lower relative particulate concentration window."
                        )
                    ),
                )
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
