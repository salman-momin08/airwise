"""Deterministic condition evaluation and memoized telemetry lookup for smart AQI alerts."""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.exceptions import ExternalProviderUnavailableError
from app.models.community_alerts import AlertRule
from app.schemas.air_quality import CurrentAirQualitySchema
from app.schemas.alerts import NotificationSeverityLiteral
from app.services.air_quality.aqi_calculator import AQIStandard
from app.services.air_quality.telemetry_service import AirQualityTelemetryService
from app.services.weather.weather_service import WeatherTelemetryService


def _eval_threshold_or_severe(
    *,
    rule: AlertRule,
    standard: AQIStandard,
    std_label: str,
    aqi: int,
    category: str | None,
    precaution: str,
) -> tuple[bool, str, str, str, NotificationSeverityLiteral]:
    severe_cutoff = 301 if standard == AQIStandard.INDIA_NAQI else 201
    if rule.alert_type == "aqi_threshold":
        cutoff = rule.threshold_value or 200
        if aqi < cutoff:
            return False, "clear", "", "", "info"
        sig = f"threshold:{rule.city.lower()}:{standard.value}:{category}:{aqi}"
        sev: NotificationSeverityLiteral = "critical" if aqi >= severe_cutoff else "warning"
        return (
            True,
            sig,
            f"{rule.city} {std_label} AQI {aqi} ({category}) Breached Threshold ({cutoff})",
            f"{precaution} Standard: {std_label} (threshold >= {cutoff}).",
            sev,
        )

    if aqi < severe_cutoff:
        return False, "clear", "", "", "info"
    sig = f"severe:{rule.city.lower()}:{standard.value}:{category}:{aqi}"
    return (
        True,
        sig,
        f"Severe Smog Episode in {rule.city}: {std_label} AQI {aqi} ({category})",
        (
            f"{precaution} Avoid outdoor cycling, jogging, or prolonged roadside "
            "exposure; prioritize indoor HEPA filtration."
        ),
        "critical",
    )


def _eval_forecast_window_or_digest(
    *,
    rule: AlertRule,
    standard: AQIStandard,
    std_label: str,
    aqi: int,
    category: str | None,
    is_stale: bool,
    precaution: str,
    max_forecast_aqi: int | None,
    inversion_risk: bool,
) -> tuple[bool, str, str, str, NotificationSeverityLiteral]:
    atype = rule.alert_type
    if atype == "forecast_deterioration":
        cutoff = rule.threshold_value or (201 if standard == AQIStandard.INDIA_NAQI else 151)
        if max_forecast_aqi is None or max_forecast_aqi < cutoff or aqi >= cutoff:
            return False, "clear", "", "", "info"
        sig = f"forecast:{rule.city.lower()}:{standard.value}:{max_forecast_aqi}"
        return (
            True,
            sig,
            f"Forecast Smog Deterioration Ahead for {rule.city}",
            (
                f"Current {std_label} AQI is {aqi}, but 24h forecast projects up to "
                f"~{max_forecast_aqi}. Complete errands earlier and seal windows tonight."
            ),
            "warning",
        )

    if atype == "clean_air_window":
        ceiling = rule.threshold_value or 100
        if aqi > ceiling or inversion_risk or is_stale:
            return False, "clear", "", "", "info"
        sig = f"clean_window:{rule.city.lower()}:{standard.value}:{category}:{aqi}"
        return (
            True,
            sig,
            f"Cleaner Outdoor Air Window in {rule.city} ({std_label} AQI {aqi})",
            (
                f"Verified {std_label} AQI is {aqi} ({category}) without thermal inversion "
                "stagnation—suitable for 15–20 minutes of cross-ventilation or errands."
            ),
            "info",
        )

    if atype == "daily_digest":
        day_tag = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        sig = f"digest:{rule.city.lower()}:{standard.value}:{day_tag}"
        return (
            True,
            sig,
            f"Daily AirWise Digest · {rule.city} ({std_label} AQI {aqi})",
            f"Current status: {category} ({std_label} AQI {aqi}). {precaution}",
            "info",
        )
    return False, "clear", "", "", "info"


def evaluate_rule_condition(
    *,
    rule: AlertRule,
    standard: AQIStandard,
    aqi: int | None,
    category: str | None,
    is_available: bool,
    is_stale: bool,
    precaution: str,
    max_forecast_aqi: int | None,
    inversion_risk: bool,
) -> tuple[bool, str, str, str, NotificationSeverityLiteral]:
    """Evaluate a single alert rule against verified telemetry and return trigger metadata."""
    std_label = "US EPA" if standard == AQIStandard.US_EPA else "India NAQI"
    if rule.alert_type == "stale_telemetry_warning":
        if is_available and not is_stale:
            return False, "clear", "", "", "info"
        stale_tag = "down" if not is_available else "stale"
        sig = f"stale:{rule.city.lower()}:{standard.value}:{stale_tag}"
        return (
            True,
            sig,
            f"Stale or Unavailable Air Telemetry in {rule.city}",
            (
                f"Live verified {std_label} station data for {rule.city} is currently "
                "delayed or unavailable. Avoid assuming outdoor air is clean until fresh "
                "measurements resume."
            ),
            "info",
        )

    if not is_available or aqi is None:
        return False, "unavailable", "", "", "info"

    if rule.alert_type in {"aqi_threshold", "severe_smog_episode"}:
        return _eval_threshold_or_severe(
            rule=rule,
            standard=standard,
            std_label=std_label,
            aqi=aqi,
            category=category,
            precaution=precaution,
        )

    return _eval_forecast_window_or_digest(
        rule=rule,
        standard=standard,
        std_label=std_label,
        aqi=aqi,
        category=category,
        is_stale=is_stale,
        precaution=precaution,
        max_forecast_aqi=max_forecast_aqi,
        inversion_risk=inversion_risk,
    )


async def resolve_rule_telemetry(
    *,
    rule: AlertRule,
    std: AQIStandard,
    aq_service: AirQualityTelemetryService,
    wx_service: WeatherTelemetryService,
    current_memo: dict[tuple[str, AQIStandard], CurrentAirQualitySchema | None],
    forecast_max_memo: dict[tuple[str, AQIStandard], int | None],
    inversion_memo: dict[str, bool],
) -> tuple[CurrentAirQualitySchema | None, int | None, bool]:
    """Fetch and memoize per-(city, standard) AQI, forecast peak, and inversion flags."""
    city_key = rule.city.strip().lower()
    aq_key = (city_key, std)
    if aq_key not in current_memo:
        try:
            current_memo[aq_key] = await aq_service.get_current_air_quality(
                city=rule.city, standard=std
            )
        except ExternalProviderUnavailableError:
            current_memo[aq_key] = None

    max_fc_aqi: int | None = None
    if rule.alert_type == "forecast_deterioration":
        if aq_key not in forecast_max_memo:
            try:
                fc = await aq_service.get_air_quality_forecast(
                    city=rule.city, standard=std, hours=24
                )
                valid_fc = [p.aqi for p in fc.points if p.aqi is not None]
                forecast_max_memo[aq_key] = max(valid_fc) if valid_fc else None
            except ExternalProviderUnavailableError:
                forecast_max_memo[aq_key] = None
        max_fc_aqi = forecast_max_memo[aq_key]

    inv_risk = False
    if rule.alert_type == "clean_air_window":
        if city_key not in inversion_memo:
            try:
                wx = await wx_service.get_current_weather(city=rule.city)
                inversion_memo[city_key] = bool(wx.inversion_risk_flag)
            except ExternalProviderUnavailableError:
                inversion_memo[city_key] = False
        inv_risk = inversion_memo[city_key]

    return current_memo[aq_key], max_fc_aqi, inv_risk
