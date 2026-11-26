from __future__ import annotations

from dataclasses import dataclass

from app.schemas.air_quality import AirQualityForecastSchema, CurrentAirQualitySchema
from app.schemas.weather import CurrentWeatherSchema
from app.services.air_quality.aqi_calculator import AQIStandard, PollutantCode


@dataclass(frozen=True)
class EnvironmentalRuleContext:
    standard: AQIStandard
    aqi: int | None
    category: str | None
    pm25_ug_m3: float | None
    is_available: bool
    is_stale: bool
    is_development_fixture: bool
    inversion_risk: bool
    has_vulnerable_member: bool
    has_hepa_purifier: bool
    budget_tier: str | None
    severity_tier: str  # "unavailable" | "good" | "moderate" | "poor" | "severe"
    block_outdoor_exertion: bool
    block_active_outdoor_commute: bool
    ventilation_guidance: str
    indoor_filtration_guidance: str
    uncertainty_disclaimer: str
    cleaner_window_note: str | None


def extract_pm25_ug_m3(current: CurrentAirQualitySchema | None) -> float | None:
    if current is None:
        return None
    for item in current.pollutants:
        if item.pollutant == PollutantCode.PM25 and item.unit == "ug/m3":
            return item.concentration
    return None


def find_cleanest_forecast_window(forecast: AirQualityForecastSchema | None) -> str | None:
    if forecast is None or not forecast.points:
        return None
    valid_points = [pt for pt in forecast.points if pt.aqi is not None]
    if not valid_points:
        return None
    best = min(valid_points, key=lambda pt: pt.aqi if pt.aqi is not None else 9999)
    hour_str = best.forecast_for.strftime("%H:%M UTC")
    return (
        f"Lowest forecast AQI window in next 24h: ~{best.aqi} "
        f"({best.category}) around {hour_str}."
    )


def evaluate_environmental_rules(
    *,
    standard: AQIStandard,
    current: CurrentAirQualitySchema | None,
    weather: CurrentWeatherSchema | None = None,
    forecast: AirQualityForecastSchema | None = None,
    has_vulnerable_member: bool = False,
    age_category: str | None = None,
    has_hepa_purifier: bool = False,
    budget_tier: str | None = None,
    cooking_type: str | None = None,
) -> EnvironmentalRuleContext:
    """Deterministic safety rule engine enforcing AirWise exposure-first hierarchy."""
    vulnerable = has_vulnerable_member or age_category in {"youth", "older_adult"}
    aqi = current.aqi if current is not None and current.status == "available" else None
    category = current.category if current is not None else None
    pm25 = extract_pm25_ug_m3(current)
    is_available = current is not None and current.status == "available" and aqi is not None
    is_stale = bool(current.is_stale) if current is not None else False
    is_fixture = bool(current.is_development_fixture) if current is not None else False
    inversion_risk = bool(weather.inversion_risk_flag) if weather is not None else False
    cleaner_window = find_cleanest_forecast_window(forecast)

    severe_cutoff = 301 if standard == AQIStandard.INDIA_NAQI else 201
    poor_cutoff = 201 if standard == AQIStandard.INDIA_NAQI else 151
    sensitive_cutoff = 101

    if not is_available or aqi is None:
        severity_tier = "unavailable"
        block_exertion = vulnerable
        block_active_commute = False
    elif aqi >= severe_cutoff or (pm25 is not None and pm25 > 150.0):
        severity_tier = "severe"
        block_exertion = True
        block_active_commute = True
    elif aqi >= poor_cutoff:
        severity_tier = "poor"
        block_exertion = True
        block_active_commute = True
    elif aqi >= sensitive_cutoff:
        severity_tier = "moderate"
        block_exertion = vulnerable
        block_active_commute = vulnerable
    else:
        severity_tier = "good"
        block_exertion = False
        block_active_commute = False

    cooking_clause = (
        " Always run the kitchen exhaust fan or chimney hood during cooking and avoid "
        "unvented indoor smoke."
        if cooking_type
        else " Avoid indoor combustion smoke (incense, mosquito coils, tobacco, unvented stoves)."
    )

    if severity_tier == "severe":
        ventilation = (
            "Keep exterior windows and leaky frames closed during severe smog. Do not open "
            "windows for cross-ventilation while outdoor particulate levels remain hazardous."
            + cooking_clause
        )
    elif severity_tier == "poor" or inversion_risk:
        ventilation = (
            "Keep windows closed during overnight/morning thermal-inversion stagnation and peak "
            "traffic hours. Only ventilate briefly (10–15 minutes) during a verified afternoon "
            "dip if outdoor haze visibly clears."
            + cooking_clause
        )
    elif severity_tier == "unavailable" or is_stale:
        ventilation = (
            "Live outdoor AQI is unavailable or stale—avoid assuming outdoor air is currently "
            "clean. Keep ventilation conservative away from traffic corridors until fresh "
            "station readings resume."
            + cooking_clause
        )
    else:
        ventilation = (
            "Outdoor air quality permits 15–25 minutes of cross-ventilation away from peak "
            "roadside traffic hours."
            + cooking_clause
        )

    if has_hepa_purifier:
        filtration = (
            "Indoor air quality is unmeasured (no indoor PM2.5 sensor connected). Run your "
            "certified HEPA purifier continuously in occupied rooms with doors/windows closed, "
            "size CADR to room volume, and pair with wet mopping/dusting."
        )
    elif budget_tier == "low":
        filtration = (
            "Indoor air quality is unmeasured (no indoor PM2.5 sensor connected). Focus on "
            "zero-cost source control first (zero indoor incense/smoking, wet mopping instead of "
            "dry sweeping, sealing window gaps). Do not rely on houseplants to filter PM2.5 and "
            "never use ozone-generating cleaners."
        )
    else:
        filtration = (
            "Indoor air quality is unmeasured (no indoor PM2.5 sensor connected). Combine strict "
            "indoor smoke source control and wet mopping with a room-sized certified HEPA "
            "purifier (avoid ozone/ionizer devices; houseplants do not meaningfully remove PM2.5)."
        )

    uncertainty_parts = [
        "Indoor air quality is unmeasured unless a dedicated indoor PM2.5 sensor is linked.",
        (
            "Filtration, masks, and routine timing reduce relative exposure "
            "but never eliminate 100% of risk."
        ),
    ]
    if not is_available:
        uncertainty_parts.insert(
            0,
            "Live verified outdoor AQI is currently unavailable; guidance uses conservative "
            "precautions without inventing local numbers.",
        )
    elif is_stale:
        uncertainty_parts.insert(
            0,
            "Latest station telemetry is marked stale; treat current outdoor "
            "conditions with caution.",
        )
    if is_fixture:
        uncertainty_parts.append(
            "Environmental snapshot comes from an explicitly labeled development fixture."
        )

    return EnvironmentalRuleContext(
        standard=standard,
        aqi=aqi,
        category=category,
        pm25_ug_m3=pm25,
        is_available=is_available,
        is_stale=is_stale,
        is_development_fixture=is_fixture,
        inversion_risk=inversion_risk,
        has_vulnerable_member=vulnerable,
        has_hepa_purifier=has_hepa_purifier,
        budget_tier=budget_tier,
        severity_tier=severity_tier,
        block_outdoor_exertion=block_exertion,
        block_active_outdoor_commute=block_active_commute,
        ventilation_guidance=ventilation,
        indoor_filtration_guidance=filtration,
        uncertainty_disclaimer=" ".join(uncertainty_parts),
        cleaner_window_note=cleaner_window,
    )
