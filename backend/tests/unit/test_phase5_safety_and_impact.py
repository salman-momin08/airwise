from __future__ import annotations

from datetime import UTC, datetime

from app.schemas.air_quality import CurrentAirQualitySchema, PollutantReadingSchema
from app.services.air_quality.aqi_calculator import AQIStandard, PollutantCode
from app.services.impact.calculators import calculate_indoor_filtration_ach
from app.services.recommendations.safety_engine import evaluate_environmental_rules

def _build_reading(
    *,
    standard: AQIStandard,
    aqi: int | None,
    pm25: float | None = None,
    status: str = "available",
    is_stale: bool = False,
) -> CurrentAirQualitySchema:
    pollutants = []
    if pm25 is not None:
        pollutants.append(
            PollutantReadingSchema(
                pollutant=PollutantCode.PM25,
                concentration=pm25,
                unit="ug/m3",
                averaging_period_hours=24,
                sub_index=aqi,
            )
        )
    return CurrentAirQualitySchema(
        city="Delhi",
        standard=standard,
        status="available" if status == "available" else "unavailable",
        aqi=aqi,
        category="Severe" if (aqi and aqi >= 301) else "Moderate",
        dominant_pollutant=PollutantCode.PM25 if pm25 is not None else None,
        pollutants=pollutants,
        measured_at=datetime.now(tz=UTC),
        provider="openaq",
        source_type="station",
        is_stale=is_stale,
        is_development_fixture=False,
        precaution_summary="Test snapshot",
    )

def test_severe_smog_and_pm25_spike_block_exertion_and_active_commute() -> None:
    rules_naqi = evaluate_environmental_rules(
        standard=AQIStandard.INDIA_NAQI,
        current=_build_reading(standard=AQIStandard.INDIA_NAQI, aqi=412, pm25=275.0),
    )
    assert rules_naqi.severity_tier == "severe"
    assert rules_naqi.block_outdoor_exertion is True
    assert rules_naqi.block_active_outdoor_commute is True
    assert "closed" in rules_naqi.ventilation_guidance.lower()
    assert "unmeasured" in rules_naqi.indoor_filtration_guidance.lower()

    # High PM2.5 (> 150 ug/m3) triggers severe override even under US EPA boundary
    rules_pm25 = evaluate_environmental_rules(
        standard=AQIStandard.US_EPA,
        current=_build_reading(standard=AQIStandard.US_EPA, aqi=195, pm25=165.0),
    )
    assert rules_pm25.severity_tier == "severe"
    assert rules_pm25.block_active_outdoor_commute is True

def test_vulnerable_household_escalates_at_moderate_aqi_and_low_budget_avoids_myths() -> None:
    rules = evaluate_environmental_rules(
        standard=AQIStandard.INDIA_NAQI,
        current=_build_reading(standard=AQIStandard.INDIA_NAQI, aqi=135, pm25=72.0),
        has_vulnerable_member=True,
        budget_tier="low",
    )
    assert rules.severity_tier == "moderate"
    assert rules.block_outdoor_exertion is True
    assert rules.block_active_outdoor_commute is True
    assert "do not rely on houseplants" in rules.indoor_filtration_guidance.lower()
    assert "never use ozone" in rules.indoor_filtration_guidance.lower()

def test_unavailable_and_stale_readings_remain_honest() -> None:
    unavailable_rules = evaluate_environmental_rules(
        standard=AQIStandard.US_EPA,
        current=None,
    )
    assert unavailable_rules.severity_tier == "unavailable"
    assert "unavailable" in unavailable_rules.uncertainty_disclaimer.lower()

    stale_rules = evaluate_environmental_rules(
        standard=AQIStandard.US_EPA,
        current=_build_reading(standard=AQIStandard.US_EPA, aqi=60, is_stale=True),
    )
    assert "stale" in stale_rules.uncertainty_disclaimer.lower()
    assert "stale" in stale_rules.ventilation_guidance.lower()

def test_indoor_filtration_steady_state_ratio_and_active_smoke_caveat() -> None:
    clean_room = calculate_indoor_filtration_ach(
        room_area_m2=20.0,
        ceiling_height_m=2.5,
        cadr_m3_per_hour=250.0,
        has_active_indoor_smoke=False,
    )
    assert clean_room.is_estimate is True
    assert clean_room.estimated_difference == 5.0
    assert clean_room.confidence == "medium"
    assert any("Steady-state I/O particle ratio" in item for item in clean_room.assumptions)

    smoky_room = calculate_indoor_filtration_ach(
        room_area_m2=20.0,
        ceiling_height_m=2.5,
        cadr_m3_per_hour=250.0,
        has_active_indoor_smoke=True,
    )
    assert smoky_room.confidence == "low"
    assert any("source elimination" in item for item in smoky_room.assumptions)
