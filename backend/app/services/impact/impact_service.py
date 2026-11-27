from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Literal, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AirWiseError, ExternalProviderUnavailableError
from app.models.planning import EmissionFactor, ImpactEstimate
from app.repositories.planning_repository import PlanningRepository
from app.schemas.impact import (
    EmissionFactorSchema,
    ExposureScreeningMetaSchema,
    HouseholdEnergyImpactRequest,
    ImpactCalculationRequest,
    ImpactEstimateSchema,
    ImpactSummarySchema,
    IndoorFiltrationImpactRequest,
    LoggedUserActionSchema,
    LogUserActionRequest,
    RelativeExposureImpactRequest,
    TransportImpactRequest,
)
from app.services.air_quality.telemetry_service import AirQualityTelemetryService
from app.services.impact.calculators import (
    ImpactResult,
    calculate_household_energy_emissions,
    calculate_indoor_filtration_ach,
    calculate_transport_emissions,
    estimate_relative_exposure_change,
)
from app.services.impact.reference_factors import (
    REFERENCE_EMISSION_FACTORS,
    REFERENCE_FACTORS_BY_CODE,
    ReferenceEmissionFactorSpec,
)
from app.services.recommendations.safety_engine import evaluate_environmental_rules

ACTIVE_OUTDOOR_MODES: frozenset[str] = frozenset(
    {"walk", "bicycle", "two_wheeler_petrol", "two_wheeler_ev"}
)

def serialize_impact_record(
    record: ImpactEstimate,
    *,
    screening: ExposureScreeningMetaSchema | None = None,
) -> ImpactEstimateSchema:
    calc_iso = (
        record.calculated_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
        if record.calculated_at.tzinfo is not None
        else record.calculated_at.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")
    )
    conf: Literal["low", "medium", "high"] = (
        cast(Literal["low", "medium", "high"], record.confidence)
        if record.confidence in {"low", "medium", "high"}
        else "medium"
    )
    return ImpactEstimateSchema(
        id=record.id,
        metric=record.metric,
        baseline_value=record.baseline_value,
        alternative_value=record.alternative_value,
        estimated_difference=record.estimated_difference,
        unit=record.unit,
        methodology=record.methodology,
        assumptions=list(record.assumptions),
        source_references=list(record.source_references),
        confidence=conf,
        is_estimate=True,
        calculated_at=calc_iso,
        exposure_screening=screening,
    )

def serialize_impact_result(
    result: ImpactResult,
    *,
    estimate_id: uuid.UUID | None = None,
    screening: ExposureScreeningMetaSchema | None = None,
) -> ImpactEstimateSchema:
    raw = asdict(result)
    return ImpactEstimateSchema(
        id=estimate_id,
        metric=str(raw["metric"]),
        baseline_value=float(raw["baseline_value"]),
        alternative_value=float(raw["alternative_value"]),
        estimated_difference=float(raw["estimated_difference"]),
        unit=str(raw["unit"]),
        methodology=str(raw["methodology"]),
        assumptions=list(result.assumptions),
        source_references=list(result.source_references),
        confidence=result.confidence,
        is_estimate=True,
        calculated_at=result.calculated_at,
        exposure_screening=screening,
    )

class ImpactEngineService:
    """Coordinates deterministic impact calculators, exposure screening, and action logs."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._repo = PlanningRepository(session)
        self._settings = settings

    async def list_emission_factors(
        self, *, category: str | None = None
    ) -> list[EmissionFactorSchema]:
        db_rows: list[EmissionFactor] = await self._repo.list_emission_factors(category=category)
        if db_rows:
            return [
                EmissionFactorSchema(
                    mode_or_region_code=row.mode_or_region_code,
                    category=row.category,
                    display_label=row.display_label,
                    factor_value=row.factor_value,
                    unit=row.unit,
                    default_occupancy=row.default_occupancy,
                    exposure_modifier=row.exposure_modifier,
                    is_active_outdoor_mode=row.mode_or_region_code in ACTIVE_OUTDOOR_MODES,
                    source_reference=row.source_reference,
                    effective_year=row.effective_year,
                )
                for row in db_rows
            ]

        specs = [
            spec
            for spec in REFERENCE_EMISSION_FACTORS
            if category is None or spec.category == category
        ]
        return [
            EmissionFactorSchema(
                mode_or_region_code=spec.mode_or_region_code,
                category=spec.category,
                display_label=spec.display_label,
                factor_value=spec.factor_value,
                unit=spec.unit,
                default_occupancy=spec.default_occupancy,
                exposure_modifier=spec.exposure_modifier,
                is_active_outdoor_mode=spec.is_active_outdoor_mode,
                source_reference=spec.source_reference,
                effective_year=spec.effective_year,
            )
            for spec in specs
        ]

    async def _resolve_factor(self, code: str) -> ReferenceEmissionFactorSpec:
        db_row = await self._repo.get_emission_factor_by_code(code)
        if db_row is not None:
            return ReferenceEmissionFactorSpec(
                category=db_row.category,
                mode_or_region_code=db_row.mode_or_region_code,
                display_label=db_row.display_label,
                factor_value=db_row.factor_value,
                unit=db_row.unit,
                default_occupancy=db_row.default_occupancy,
                exposure_modifier=db_row.exposure_modifier,
                is_active_outdoor_mode=db_row.mode_or_region_code in ACTIVE_OUTDOOR_MODES,
                source_reference=db_row.source_reference,
                effective_year=db_row.effective_year,
            )
        spec = REFERENCE_FACTORS_BY_CODE.get(code)
        if spec is None:
            raise AirWiseError(
                code="UNKNOWN_EMISSION_FACTOR",
                message=f"Emission factor '{code}' is not in the verified reference table.",
                status_code=422,
            )
        return spec

    async def _screen_transport_exposure(
        self, payload: TransportImpactRequest
    ) -> ExposureScreeningMetaSchema | None:
        if payload.city is None and payload.alternative_mode is None:
            return None

        current = None
        if payload.city is not None:
            try:
                current = await AirQualityTelemetryService(
                    self._session, self._settings
                ).get_current_air_quality(city=payload.city, standard=payload.standard)
            except ExternalProviderUnavailableError:
                current = None

        rules = evaluate_environmental_rules(
            standard=payload.standard,
            current=current,
        )
        alt_is_active_outdoor = payload.alternative_mode in ACTIVE_OUTDOOR_MODES
        recommended = True
        warning: str | None = None
        safer_fallback: str | None = None

        if alt_is_active_outdoor and rules.block_active_outdoor_commute:
            recommended = False
            warning = (
                f"Exposure-First Safety Override: {payload.alternative_mode} reduces tailpipe "
                f"CO2e, but current pollution ({payload.standard.value}"
                f"{f'={rules.aqi}' if rules.aqi is not None else ''}) makes open roadside "
                "walking, cycling, or two-wheeler travel unsafe due to elevated inhaled PM2.5."
            )
            safer_fallback = (
                "Choose enclosed Urban Metro/Rail, public bus with a well-fitted N95/FFP2 "
                "respirator, or work-from-home until ambient AQI improves."
            )
        elif payload.city is not None and not rules.is_available:
            warning = (
                "Live city AQI is currently unavailable; verify local outdoor conditions before "
                "choosing open-air active mobility."
            )
        elif rules.is_stale:
            warning = (
                "Latest AQI reading is stale; exercise caution with prolonged roadside exposure."
            )

        return ExposureScreeningMetaSchema(
            evaluated=payload.city is not None,
            city=payload.city,
            standard=payload.standard,
            aqi=rules.aqi,
            category=rules.category,
            is_stale=rules.is_stale,
            is_development_fixture=rules.is_development_fixture,
            recommended_for_current_aqi=recommended,
            exposure_warning=warning,
            safer_commute_fallback=safer_fallback,
            indoor_air_measured=False,
        )

    async def calculate(
        self, payload: ImpactCalculationRequest
    ) -> tuple[ImpactResult, ExposureScreeningMetaSchema | None]:
        if isinstance(payload, TransportImpactRequest):
            if payload.baseline_mode is not None and payload.alternative_mode is not None:
                base_spec = await self._resolve_factor(payload.baseline_mode)
                alt_spec = await self._resolve_factor(payload.alternative_mode)
                base_occ = payload.baseline_occupancy or base_spec.default_occupancy or 1.0
                alt_occ = payload.alternative_occupancy or alt_spec.default_occupancy or 1.0
                base_vkm = (
                    base_spec.factor_value * base_occ
                    if base_spec.unit == "kg_co2e_per_pkm"
                    else base_spec.factor_value
                )
                alt_vkm = (
                    alt_spec.factor_value * alt_occ
                    if alt_spec.unit == "kg_co2e_per_pkm"
                    else alt_spec.factor_value
                )
                source_ref = f"{base_spec.source_reference}; {alt_spec.source_reference}"
            else:
                base_vkm = float(payload.baseline_vkm_factor_kg_co2e or 0.0)
                base_occ = float(payload.baseline_occupancy or 1.0)
                alt_vkm = float(payload.alternative_vkm_factor_kg_co2e or 1.0)
                alt_occ = float(payload.alternative_occupancy or 1.0)
                source_ref = payload.factor_source_reference

            result = calculate_transport_emissions(
                distance_km=payload.distance_km,
                baseline_vkm_factor_kg_co2e=base_vkm,
                baseline_occupancy=base_occ,
                alternative_vkm_factor_kg_co2e=alt_vkm,
                alternative_occupancy=alt_occ,
                factor_source_reference=source_ref,
            )
            screening = await self._screen_transport_exposure(payload)
            return result, screening

        if isinstance(payload, HouseholdEnergyImpactRequest):
            if payload.grid_emission_factor_kg_per_kwh is not None:
                grid_factor = payload.grid_emission_factor_kg_per_kwh
                grid_ref = payload.grid_source_reference
            else:
                grid_spec = await self._resolve_factor(
                    payload.grid_region_code or "india_cea_grid_avg"
                )
                grid_factor = grid_spec.factor_value
                grid_ref = grid_spec.source_reference
            result = calculate_household_energy_emissions(
                baseline_power_kw=payload.baseline_power_kw,
                alternative_power_kw=payload.alternative_power_kw,
                operating_hours=payload.operating_hours,
                grid_emission_factor_kg_per_kwh=grid_factor,
                grid_source_reference=grid_ref,
            )
            return result, None

        if isinstance(payload, IndoorFiltrationImpactRequest):
            result = calculate_indoor_filtration_ach(
                room_area_m2=payload.room_area_m2,
                ceiling_height_m=payload.ceiling_height_m,
                cadr_m3_per_hour=payload.cadr_m3_per_hour,
                infiltration_ach=payload.infiltration_ach,
                penetration_factor=payload.penetration_factor,
                deposition_rate_per_hour=payload.deposition_rate_per_hour,
                has_active_indoor_smoke=payload.has_active_indoor_smoke,
            )
            return result, ExposureScreeningMetaSchema(
                evaluated=False,
                recommended_for_current_aqi=True,
                indoor_air_measured=False,
                exposure_warning=(
                    "Indoor air quality has not been measured (no indoor PM2.5 sensor linked). "
                    "Eliminate indoor smoke sources before relying on portable filtration."
                    if payload.has_active_indoor_smoke
                    else "Indoor air quality has not been measured (no indoor PM2.5 sensor linked)."
                ),
            )

        if isinstance(payload, RelativeExposureImpactRequest):
            result = estimate_relative_exposure_change(
                outdoor_pm25_ug_m3=payload.outdoor_pm25_ug_m3,
                duration_hours=payload.duration_hours,
                baseline_env_modifier=payload.baseline_env_modifier,
                alternative_env_modifier=payload.alternative_env_modifier,
                assumption_note=payload.assumption_note,
            )
            return result, ExposureScreeningMetaSchema(
                evaluated=False,
                recommended_for_current_aqi=True,
                indoor_air_measured=False,
            )

        raise AirWiseError(
            code="UNSUPPORTED_CALCULATOR",
            message="Unsupported impact calculator type.",
            status_code=422,
        )

    async def persist_impact_result(
        self,
        *,
        user_id: uuid.UUID | None,
        user_action_id: uuid.UUID | None,
        result: ImpactResult,
    ) -> ImpactEstimate:
        return await self._repo.create_impact_estimate(
            user_id=user_id,
            user_action_id=user_action_id,
            metric=result.metric,
            baseline_value=result.baseline_value,
            alternative_value=result.alternative_value,
            estimated_difference=result.estimated_difference,
            unit=result.unit,
            methodology=result.methodology,
            assumptions=list(result.assumptions),
            source_references=list(result.source_references),
            confidence=result.confidence,
            calculated_at=datetime.now(tz=UTC),
        )

    async def log_user_action(
        self,
        *,
        user_id: uuid.UUID,
        payload: LogUserActionRequest,
    ) -> LoggedUserActionSchema:
        occurred = payload.occurred_at or datetime.now(tz=UTC)
        if occurred.tzinfo is None:
            occurred = occurred.replace(tzinfo=UTC)
        action = await self._repo.create_user_action(
            user_id=user_id,
            action_type=payload.action_type,
            title=payload.title,
            quantity=payload.quantity,
            unit=payload.unit,
            occurred_at=occurred,
        )
        estimate_schema: ImpactEstimateSchema | None = None
        if payload.calculation is not None:
            calc_result, screening = await self.calculate(payload.calculation)
            record = await self.persist_impact_result(
                user_id=user_id,
                user_action_id=action.id,
                result=calc_result,
            )
            estimate_schema = serialize_impact_record(record, screening=screening)

        await self._session.commit()
        return LoggedUserActionSchema(
            id=action.id,
            action_type=action.action_type,
            title=action.title,
            quantity=action.quantity,
            unit=action.unit,
            is_self_reported=True,
            occurred_at=action.occurred_at,
            impact_estimate=estimate_schema,
        )

    async def get_user_summary(self, *, user_id: uuid.UUID) -> ImpactSummarySchema:
        actions = await self._repo.list_user_actions(user_id=user_id, limit=500)
        transport_saved = 0.0
        energy_saved = 0.0
        exposure_count = 0
        for act in actions:
            for est in act.estimates:
                if est.metric == "transport_co2e" and est.estimated_difference > 0:
                    transport_saved += est.estimated_difference
                elif est.metric == "household_energy_co2e" and est.estimated_difference > 0:
                    energy_saved += est.estimated_difference
                elif est.metric == "relative_exposure_index" and est.estimated_difference > 0:
                    exposure_count += 1

        total_saved = round(transport_saved + energy_saved, 4)
        return ImpactSummarySchema(
            total_logged_actions=len(actions),
            estimated_avoided_co2e_kg=total_saved,
            transport_avoided_co2e_kg=round(transport_saved, 4),
            energy_avoided_co2e_kg=round(energy_saved, 4),
            relative_exposure_reductions_count=exposure_count,
            is_estimate=True,
        )

    async def get_user_history(
        self, *, user_id: uuid.UUID, limit: int = 50
    ) -> list[LoggedUserActionSchema]:
        actions = await self._repo.list_user_actions(user_id=user_id, limit=limit)
        items: list[LoggedUserActionSchema] = []
        for act in actions:
            est_schema = (
                serialize_impact_record(act.estimates[0]) if act.estimates else None
            )
            items.append(
                LoggedUserActionSchema(
                    id=act.id,
                    action_type=act.action_type,
                    title=act.title,
                    quantity=act.quantity,
                    unit=act.unit,
                    is_self_reported=True,
                    occurred_at=act.occurred_at,
                    impact_estimate=est_schema,
                )
            )
        return items
