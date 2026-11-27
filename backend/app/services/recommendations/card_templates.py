"""Deterministic recommendation card templates, AI-reason guardrails, and commute screening."""

from __future__ import annotations

import re
import uuid

from app.ai.guardrails.grounding import is_injection
from app.ai.guardrails.safety_rules import contains_prohibited_scientific_claim
from app.schemas.recommendations import (
    RecommendationCategoryLiteral,
    RecommendationPriorityLiteral,
    ScreenedAlternativeSchema,
)
from app.services.recommendations.safety_engine import EnvironmentalRuleContext

PRIORITY_ORDER: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}

_NUMBER_CLAIM = re.compile(
    r"\d|https?://|<[^>]*>|\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"twenty|thirty|forty|fifty|hundred|thousand|percent|percentage)\b",
    re.IGNORECASE,
)


def is_safe_ai_reason(reason: str) -> bool:
    """Validate that optional AI-phrased explanation text introduces no numbers or unsafe myths."""
    cleaned = re.sub(r"PM2\.5|PM10|CO2e?|N95|FFP2|HEPA", "", reason, flags=re.IGNORECASE)
    if _NUMBER_CLAIM.search(cleaned):
        return False
    if is_injection(reason) or contains_prohibited_scientific_claim(reason):
        return False
    lowered = reason.lower()
    return not ("indoor air is safe" in lowered or ("drop" in lowered and "street" in lowered))


def build_deterministic_card_specs(
    *,
    rules: EnvironmentalRuleContext,
    transport_estimate_id: uuid.UUID,
    filtration_estimate_id: uuid.UUID,
    energy_estimate_id: uuid.UUID,
) -> dict[RecommendationCategoryLiteral, dict[str, object]]:
    """Construct exposure-first deterministic recommendation specs across all 5 categories."""
    top_priority: RecommendationPriorityLiteral = (
        "critical"
        if rules.severity_tier == "severe"
        else ("high" if rules.severity_tier in {"poor", "unavailable"} else "medium")
    )

    return {
        "routine": {
            "priority": top_priority,
            "title": (
                "Shift Strenuous Activity Indoors & Protect Vulnerable Household Members"
                if rules.block_outdoor_exertion
                else "Schedule Outdoor Activity Around Validated Dispersion Windows"
            ),
            "reason": (
                "Outdoor particulate exposure risk is elevated; moving heavy breathing "
                "activities indoors lowers cumulative PM2.5 inhalation."
                if rules.block_outdoor_exertion
                else "Verified ambient conditions allow moderate outdoor routines away from "
                "congested arterial corridors."
            ),
            "action_steps": [
                (
                    "Replace outdoor running or playground exertion with indoor movement."
                    if rules.block_outdoor_exertion
                    else "Prefer parks away from roadside tailpipe corridors."
                ),
                rules.cleaner_window_note
                or "Check hourly AQI freshness before extending outdoor duration.",
                (
                    "Wear a well-fitted N95/FFP2 respirator if prolonged "
                    "outdoor travel is unavoidable."
                ),
            ],
            "safer_alternative": (
                "Generate and review a Morning–Night draft in the Daily Routine Planner."
            ),
            "impact_estimate_id": None,
        },
        "transport": {
            "priority": "critical" if rules.block_active_outdoor_commute else "medium",
            "title": (
                "Choose Enclosed Metro/Public Transit Over Walking or Cycling in Smog"
                if rules.block_active_outdoor_commute
                else "Substitute Urban Rail or Shared Transit for Solo Car Trips"
            ),
            "reason": (
                "Personal exposure safety overrides active-mobility CO2e savings during "
                "poor or severe pollution; enclosed rail transit cuts solo-car CO2e without "
                "unfiltered roadside exertion."
                if rules.block_active_outdoor_commute
                else "Shifting passenger kilometers from solo petrol driving to urban rail or "
                "bus transit lowers per-trip CO2e emissions."
            ),
            "action_steps": [
                (
                    "Avoid roadside cycling, long walks, and open two-wheelers until AQI improves."
                    if rules.block_active_outdoor_commute
                    else "Compare door-to-door rail, bus, carpool, and active options."
                ),
                "Use enclosed metro/rail or carpool when commuting cannot be deferred.",
                "Keep cabin air on recirculation when passing congested traffic corridors.",
            ],
            "safer_alternative": "Work from home if your schedule allows during smog spikes.",
            "impact_estimate_id": transport_estimate_id,
        },
        "indoor_air": {
            "priority": "high" if rules.severity_tier in {"severe", "poor"} else "medium",
            "title": "Eliminate Indoor Smoke Sources & Size HEPA Filtration to Room Volume",
            "reason": rules.indoor_filtration_guidance,
            "action_steps": [
                rules.ventilation_guidance,
                "Use damp mopping and microfiber wiping instead of dry sweeping.",
                "Size portable HEPA CADR to bedroom/living-room volume; avoid ozone cleaners.",
            ],
            "safer_alternative": (
                "Prioritize sealing window leaks and stopping indoor "
                "incense/combustion at zero cost."
            ),
            "impact_estimate_id": filtration_estimate_id,
        },
        "household_sustainability": {
            "priority": "low" if rules.severity_tier == "severe" else "medium",
            "title": "Trim Peak Appliance Wattage & Use Covered Clean Cooking",
            "reason": (
                "Moderate HVAC setpoints and efficient induction/covered cooking reduce "
                "household electricity demand and indoor combustion fumes simultaneously."
            ),
            "action_steps": [
                "Run high-wattage water heaters or laundry outside evening grid-peak hours.",
                "Use lids and exhaust ventilation while cooking to cut energy and indoor haze.",
                "Maintain clean AC and purifier pre-filters so fans draw less power.",
            ],
            "safer_alternative": (
                "Never disable essential HEPA filtration solely to save electricity during smog."
            ),
            "impact_estimate_id": energy_estimate_id,
        },
        "community": {
            "priority": "low",
            "title": "Join Voluntary Neighborhood No-Idling & Clean-Commute Actions",
            "reason": (
                "Coordinated school-gate no-idling and shared transit habits reduce local "
                "tailpipe emissions near pedestrians without claiming a single household can "
                "measurably drop city-wide ambient AQI."
            ),
            "action_steps": [
                (
                    "Switch off vehicle engines when waiting more than 30 seconds "
                    "at school or market drop-offs."
                ),
                "Coordinate a voluntary 3-person neighborhood carpool or metro buddy group.",
                "Share verified AQI standard & staleness context with Older Adult neighbors.",
            ],
            "safer_alternative": (
                "Participate remotely during severe smog alerts rather than gathering outdoors."
            ),
            "impact_estimate_id": None,
        },
    }


def build_screened_transport_alternatives(
    *,
    distance_km: float,
    cycle_safe: bool,
    metro_diff_kg: float,
    carpool_diff_kg: float,
    cycle_diff_kg: float,
) -> list[ScreenedAlternativeSchema]:
    """Build exposure-screened transport alternatives ordered by enclosed smog safety."""
    note = f"{distance_km:.1f} km vs solo petrol car (is_estimate=true)"
    return [
        ScreenedAlternativeSchema(
            category="transport",
            option_code="metro_rail",
            title="Urban Metro / Rail Transit (Enclosed Cabin)",
            exposure_safe_now=True,
            safety_rationale=(
                "Enclosed rail protects against direct roadside exhaust and heavy breathing "
                "exposure during poor/severe pollution."
            ),
            estimated_co2e_difference_kg=metro_diff_kg,
            assumptions_note=note,
        ),
        ScreenedAlternativeSchema(
            category="transport",
            option_code="carpool_3",
            title="3-Person Shared Carpool (Recirculate Cabin Air)",
            exposure_safe_now=True,
            safety_rationale=(
                "Divides per-passenger vehicle emissions by 3 inside an enclosed cabin."
            ),
            estimated_co2e_difference_kg=carpool_diff_kg,
            assumptions_note=note,
        ),
        ScreenedAlternativeSchema(
            category="transport",
            option_code="bicycle",
            title="Active Cycling Commute",
            exposure_safe_now=cycle_safe,
            safety_rationale=(
                "Blocked right now: exposure safety overrides zero-tailpipe CO2e during "
                "elevated or unverified outdoor pollution."
                if not cycle_safe
                else "Outdoor AQI is verified within acceptable bounds for active cycling."
            ),
            estimated_co2e_difference_kg=cycle_diff_kg,
            assumptions_note=note,
        ),
    ]
