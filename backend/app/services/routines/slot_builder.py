"""Deterministic Morning–Night routine slot builders and window comparison helpers."""

from __future__ import annotations

import uuid
from datetime import time

from app.models.planning import RoutineActivity
from app.schemas.air_quality import AirQualityForecastSchema
from app.schemas.routines import (
    ConfidenceLiteral,
    RoutineActivityInput,
    RoutineWindowOptionSchema,
    TimeBlockLiteral,
)
from app.services.air_quality.aqi_calculator import AQIStandard
from app.services.recommendations.safety_engine import EnvironmentalRuleContext


def parse_hhmm(value: str, fallback: time) -> time:
    """Parse an `HH:MM` string into `datetime.time`, falling back safely on invalid input."""
    try:
        parts = value.split(":")
        return time(hour=int(parts[0]), minute=int(parts[1]))
    except (ValueError, IndexError):
        return fallback


def build_default_routine_slots(
    *,
    routine_id: uuid.UUID,
    rules: EnvironmentalRuleContext,
    work_start: time,
    school_note: str,
    exposure_est_id: uuid.UUID | None,
    commute_est_id: uuid.UUID | None,
) -> list[RoutineActivity]:
    """Synthesize the 5 deterministic Morning–Night routine slots under exposure-first rules."""
    conf: ConfidenceLiteral = "low" if (not rules.is_available or rules.is_stale) else "medium"
    morning_outdoor_blocked = rules.block_outdoor_exertion or rules.inversion_risk
    return [
        RoutineActivity(
            id=uuid.uuid4(),
            routine_id=routine_id,
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
            routine_id=routine_id,
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
            routine_id=routine_id,
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
            routine_id=routine_id,
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
                "Evening rush-hour emissions combine with cooling air to trap surface pollutants."
            ),
            impact_estimate_id=None,
            confidence=conf,
        ),
        RoutineActivity(
            id=uuid.uuid4(),
            routine_id=routine_id,
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


def build_edited_routine_slots(
    *,
    routine_id: uuid.UUID,
    standard: AQIStandard,
    snap_aqi: int | None,
    slots: list[RoutineActivityInput],
) -> list[RoutineActivity]:
    """Validate user-edited routine slots against snapshot AQI and attach exposure warnings."""
    severe_cutoff = 301 if standard == AQIStandard.INDIA_NAQI else 201
    poor_cutoff = 201 if standard == AQIStandard.INDIA_NAQI else 151
    elevated_pollution = snap_aqi is not None and snap_aqi >= poor_cutoff

    replacement: list[RoutineActivity] = []
    for idx, slot in enumerate(slots):
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
                f"pollution ({standard.value}={snap_aqi}). Consider shifting indoors or wearing "
                "a well-fitted N95/FFP2 respirator."
            )
            if not safer:
                safer = "Substitute indoor activity or enclosed filtered transit."

        replacement.append(
            RoutineActivity(
                id=uuid.uuid4(),
                routine_id=routine_id,
                slot_order=idx,
                time_block=slot.time_block,
                start_time=parse_hhmm(slot.start_time, time(8, 0)),
                duration_minutes=slot.duration_minutes,
                title=slot.title,
                environment_type=slot.environment_type,
                exposure_note="User-customized activity slot screened against snapshot AQI.",
                safer_alternative=safer,
                explanation="Explicitly edited by user.",
                safety_warning=warning,
                impact_estimate_id=None,
                confidence="medium" if snap_aqi is not None else "low",
            )
        )
    return replacement


def build_window_comparison_options(
    *,
    standard: AQIStandard,
    rules: EnvironmentalRuleContext,
    forecast: AirQualityForecastSchema | None,
) -> list[RoutineWindowOptionSchema]:
    """Compare Morning–Night windows against forecast points and inversion conditions."""
    blocks: tuple[tuple[TimeBlockLiteral, str], ...] = (
        ("morning", "06:30–09:30"),
        ("midday", "11:30–13:30"),
        ("afternoon", "14:00–16:30"),
        ("evening", "17:30–20:30"),
        ("night", "21:00–06:00"),
    )
    poor_cutoff = 201 if standard == AQIStandard.INDIA_NAQI else 151
    windows: list[RoutineWindowOptionSchema] = []
    for idx, (block, label) in enumerate(blocks):
        pt = (
            forecast.points[min(idx * 3, len(forecast.points) - 1)]
            if forecast is not None and forecast.points
            else None
        )
        slot_aqi = pt.aqi if pt is not None and pt.aqi is not None else rules.aqi
        slot_cat = pt.category if pt is not None and pt.category is not None else rules.category
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
    return windows
