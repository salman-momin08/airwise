from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_app_settings, get_response_meta
from app.core.config import Settings
from app.integrations.air_quality.provider import resolve_air_quality_adapter
from app.schemas.air_quality import CurrentAirQualitySchema, PollutantReadingSchema
from app.schemas.common import ApiResponse, ResponseMeta
from app.services.air_quality.aqi_calculator import AQIStandard, calculate_aqi

router = APIRouter(prefix="/air-quality", tags=["air-quality"])


def _precaution_for_aqi(standard: AQIStandard, aqi: int | None) -> str:
    if aqi is None:
        return (
            "Verified AQI is currently unavailable. Limit heavy smoke exposure "
            "and check back shortly."
        )
    severe_cutoff = 301 if standard == AQIStandard.INDIA_NAQI else 201
    poor_cutoff = 201 if standard == AQIStandard.INDIA_NAQI else 151
    moderate_cutoff = 101
    if aqi >= severe_cutoff:
        return (
            "Severe pollution: shift exercise indoors, keep windows closed unless filtering, "
            "and wear a well-fitted N95/FFP2 respirator if outdoors."
        )
    if aqi >= poor_cutoff:
        return (
            "Elevated pollution: avoid prolonged outdoor exertion and prioritize enclosed "
            "transit over roadside cycling or walking."
        )
    if aqi >= moderate_cutoff:
        return (
            "Moderate pollution: children, older adults, and sensitive individuals should "
            "reduce prolonged heavy outdoor exertion."
        )
    return "Air quality is suitable for normal outdoor activities."


@router.get("/current", response_model=ApiResponse[CurrentAirQualitySchema])
async def get_current_air_quality(
    city: Annotated[
        str,
        Query(min_length=2, max_length=100, description="City name (e.g., Delhi, Bengaluru)"),
    ],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
    standard: Annotated[AQIStandard, Query()] = AQIStandard.INDIA_NAQI,
) -> ApiResponse[CurrentAirQualitySchema]:
    adapter = resolve_air_quality_adapter(settings)
    raw = await adapter.fetch_city_measurements(city)
    calc = calculate_aqi(standard=standard, measurements=raw.measurements)

    pollutant_items = [
        PollutantReadingSchema(
            pollutant=code,
            concentration=conc,
            unit=unit,
            averaging_period_hours=8 if code.value in {"co", "o3"} else 24,
            sub_index=calc.sub_indices[code].sub_index if code in calc.sub_indices else None,
        )
        for code, (conc, unit) in raw.measurements.items()
    ]

    data = CurrentAirQualitySchema(
        city=raw.city,
        location_precision="city",
        standard=standard,
        status="available" if calc.status == "available" else "unavailable",
        aqi=calc.aqi,
        category=calc.category,
        dominant_pollutant=calc.dominant_pollutant,
        pollutants=pollutant_items,
        measured_at=raw.measured_at,
        provider=raw.provider,
        source_type="station" if raw.source_type == "station" else "model",
        is_stale=raw.is_stale,
        is_development_fixture=raw.is_development_fixture,
        precaution_summary=_precaution_for_aqi(standard, calc.aqi),
        unavailable_reason=calc.unavailable_reason,
    )
    return ApiResponse(data=data, meta=meta)
