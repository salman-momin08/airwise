from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

ConfidenceLevel = Literal["low", "medium", "high"]

@dataclass(frozen=True)
class ImpactResult:
    """Deterministic environmental impact estimate schema (LLM-immutable)."""

    metric: str
    baseline_value: float
    alternative_value: float
    estimated_difference: float
    unit: str
    methodology: str
    assumptions: list[str]
    source_references: list[str]
    confidence: ConfidenceLevel
    is_estimate: bool = True
    calculated_at: str = field(
        default_factory=lambda: datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
    )

def calculate_transport_emissions(
    *,
    distance_km: float,
    baseline_vkm_factor_kg_co2e: float,
    baseline_occupancy: float,
    alternative_vkm_factor_kg_co2e: float,
    alternative_occupancy: float,
    factor_source_reference: str,
) -> ImpactResult:
    """Calculate passenger-kilometer CO2e difference between two transport options."""
    if distance_km < 0:
        raise ValueError("distance_km must be non-negative.")
    if baseline_occupancy <= 0 or alternative_occupancy <= 0:
        raise ValueError("Vehicle occupancy must be strictly positive.")
    if baseline_vkm_factor_kg_co2e < 0 or alternative_vkm_factor_kg_co2e < 0:
        raise ValueError("Emission factors must be non-negative.")

    baseline_pkm_factor = baseline_vkm_factor_kg_co2e / baseline_occupancy
    alternative_pkm_factor = alternative_vkm_factor_kg_co2e / alternative_occupancy

    baseline_kg = round(distance_km * baseline_pkm_factor, 4)
    alternative_kg = round(distance_km * alternative_pkm_factor, 4)
    difference_kg = round(baseline_kg - alternative_kg, 4)

    return ImpactResult(
        metric="transport_co2e",
        baseline_value=baseline_kg,
        alternative_value=alternative_kg,
        estimated_difference=difference_kg,
        unit="kg_co2e",
        methodology="passenger_km_emission_factor",
        assumptions=[
            f"Trip distance: {distance_km:.2f} km",
            f"Baseline occupancy: {baseline_occupancy:.2f} passenger(s)",
            f"Alternative occupancy: {alternative_occupancy:.2f} passenger(s)",
        ],
        source_references=[factor_source_reference],
        confidence="medium",
    )

def calculate_household_energy_emissions(
    *,
    baseline_power_kw: float,
    alternative_power_kw: float,
    operating_hours: float,
    grid_emission_factor_kg_per_kwh: float,
    grid_source_reference: str,
) -> ImpactResult:
    """Calculate electricity-driven CO2e savings from lower appliance load or duration."""
    if operating_hours < 0 or baseline_power_kw < 0 or alternative_power_kw < 0:
        raise ValueError("Power ratings and operating hours must be non-negative.")
    if grid_emission_factor_kg_per_kwh < 0:
        raise ValueError("Grid emission factor must be non-negative.")

    baseline_kwh = baseline_power_kw * operating_hours
    alt_kwh = alternative_power_kw * operating_hours

    baseline_kg = round(baseline_kwh * grid_emission_factor_kg_per_kwh, 4)
    alt_kg = round(alt_kwh * grid_emission_factor_kg_per_kwh, 4)

    return ImpactResult(
        metric="household_energy_co2e",
        baseline_value=baseline_kg,
        alternative_value=alt_kg,
        estimated_difference=round(baseline_kg - alt_kg, 4),
        unit="kg_co2e",
        methodology="power_kw_hours_times_grid_factor",
        assumptions=[
            f"Operating hours: {operating_hours:.2f} h",
            f"Baseline energy: {baseline_kwh:.3f} kWh vs Alternative: {alt_kwh:.3f} kWh",
            f"Grid emission factor: {grid_emission_factor_kg_per_kwh:.4f} kg CO2e/kWh",
        ],
        source_references=[grid_source_reference],
        confidence="medium",
    )

def calculate_indoor_filtration_ach(
    *,
    room_area_m2: float,
    ceiling_height_m: float,
    cadr_m3_per_hour: float,
    infiltration_ach: float = 0.6,
    penetration_factor: float = 0.8,
    deposition_rate_per_hour: float = 0.2,
    has_active_indoor_smoke: bool = False,
) -> ImpactResult:
    """Estimate clean air changes per hour (ACH) added by a HEPA purifier."""
    if room_area_m2 <= 0 or ceiling_height_m <= 0:
        raise ValueError("Room area and ceiling height must be positive.")
    if cadr_m3_per_hour < 0:
        raise ValueError("CADR must be non-negative.")
    if infiltration_ach < 0 or penetration_factor < 0 or deposition_rate_per_hour < 0:
        raise ValueError("Infiltration, penetration, and deposition inputs must be non-negative.")

    volume_m3 = room_area_m2 * ceiling_height_m
    ach = round(cadr_m3_per_hour / volume_m3, 2)
    denom = infiltration_ach + deposition_rate_per_hour + ach
    steady_state_ratio = (
        round((penetration_factor * infiltration_ach) / denom, 2) if denom > 0 else 1.0
    )

    assumptions = [
        (
            f"Room volume: {volume_m3:.1f} m3 "
            f"({room_area_m2:.1f} m2 x {ceiling_height_m:.2f} m)"
        ),
        f"Purifier CADR: {cadr_m3_per_hour:.0f} m3/h on selected speed",
        (
            f"Steady-state I/O particle ratio approximation: ~{steady_state_ratio:.2f} "
            f"(infiltration={infiltration_ach:.2f}/h, penetration={penetration_factor:.2f}, "
            f"deposition={deposition_rate_per_hour:.2f}/h)"
        ),
        "Indoor air quality is unmeasured unless a dedicated indoor PM2.5 sensor is connected.",
        "Represents clean-air delivery rate per room volume, not a clinical guarantee.",
    ]
    if has_active_indoor_smoke:
        assumptions.append(
            "Active indoor combustion/smoke reported: prioritize source elimination "
            "(stop incense, smoking, or unvented smoke) before relying on filtration."
        )
    else:
        assumptions.append(
            "Assumes closed exterior windows, clean filter media, and no active indoor smoke."
        )

    return ImpactResult(
        metric="indoor_filtration_ach",
        baseline_value=0.0,
        alternative_value=ach,
        estimated_difference=ach,
        unit="clean_air_changes_per_hour",
        methodology="cadr_divided_by_room_volume",
        assumptions=assumptions,
        source_references=["US EPA Guide to Air Cleaners in the Home (CADR/ACH sizing)"],
        confidence="low" if has_active_indoor_smoke else "medium",
    )

def estimate_relative_exposure_change(
    *,
    outdoor_pm25_ug_m3: float,
    duration_hours: float,
    baseline_env_modifier: float,
    alternative_env_modifier: float,
    assumption_note: str,
) -> ImpactResult:
    """Compare time-weighted PM2.5 concentration index (ug*h/m3) across two routines."""
    if outdoor_pm25_ug_m3 < 0 or duration_hours < 0:
        raise ValueError("Concentration and duration must be non-negative.")
    if baseline_env_modifier < 0 or alternative_env_modifier < 0:
        raise ValueError("Environment modifiers must be non-negative.")

    baseline_idx = round(outdoor_pm25_ug_m3 * duration_hours * baseline_env_modifier, 2)
    alt_idx = round(outdoor_pm25_ug_m3 * duration_hours * alternative_env_modifier, 2)

    return ImpactResult(
        metric="relative_exposure_index",
        baseline_value=baseline_idx,
        alternative_value=alt_idx,
        estimated_difference=round(baseline_idx - alt_idx, 2),
        unit="ug_h_per_m3",
        methodology="time_weighted_microenvironment_concentration",
        assumptions=[
            (
                f"Ambient PM2.5 concentration: {outdoor_pm25_ug_m3:.1f} ug/m3 "
                f"over {duration_hours:.2f} h"
            ),
            assumption_note,
            (
                "Relative ambient exposure index; does not claim exact inhaled lung dose "
                "without breathing-rate telemetry."
            ),
        ],
        source_references=[
            "WHO Global Air Quality Guidelines (2021) — Exposure Reduction Principles"
        ],
        confidence="low",
    )
