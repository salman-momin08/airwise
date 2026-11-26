from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReferenceEmissionFactorSpec:
    category: str
    mode_or_region_code: str
    display_label: str
    factor_value: float
    unit: str
    default_occupancy: float | None
    exposure_modifier: float | None
    is_active_outdoor_mode: bool
    source_reference: str
    effective_year: int


REFERENCE_EMISSION_FACTORS: tuple[ReferenceEmissionFactorSpec, ...] = (
    ReferenceEmissionFactorSpec(
        category="transport",
        mode_or_region_code="car_solo_petrol",
        display_label="Solo Petrol Car",
        factor_value=0.168,
        unit="kg_co2e_per_vkm",
        default_occupancy=1.0,
        exposure_modifier=0.55,
        is_active_outdoor_mode=False,
        source_reference="India GHG Program — Road Transport Emission Factors (2024)",
        effective_year=2024,
    ),
    ReferenceEmissionFactorSpec(
        category="transport",
        mode_or_region_code="car_ev",
        display_label="Electric Car (Grid-Charged)",
        factor_value=0.078,
        unit="kg_co2e_per_vkm",
        default_occupancy=1.2,
        exposure_modifier=0.50,
        is_active_outdoor_mode=False,
        source_reference="IEA / India Grid-Adjusted EV Lifecycle Operational Factor (2024)",
        effective_year=2024,
    ),
    ReferenceEmissionFactorSpec(
        category="transport",
        mode_or_region_code="carpool_3",
        display_label="Shared Carpool (3 Occupants)",
        factor_value=0.168,
        unit="kg_co2e_per_vkm",
        default_occupancy=3.0,
        exposure_modifier=0.55,
        is_active_outdoor_mode=False,
        source_reference="India GHG Program — Shared Passenger Vehicle Factor (2024)",
        effective_year=2024,
    ),
    ReferenceEmissionFactorSpec(
        category="transport",
        mode_or_region_code="bus",
        display_label="Public City Bus (CNG / Electric Blend)",
        factor_value=0.042,
        unit="kg_co2e_per_pkm",
        default_occupancy=1.0,
        exposure_modifier=0.60,
        is_active_outdoor_mode=False,
        source_reference="IPCC / Urban Public Bus Passenger-km Factor (2024)",
        effective_year=2024,
    ),
    ReferenceEmissionFactorSpec(
        category="transport",
        mode_or_region_code="metro_rail",
        display_label="Urban Metro / Suburban Rail",
        factor_value=0.028,
        unit="kg_co2e_per_pkm",
        default_occupancy=1.0,
        exposure_modifier=0.38,
        is_active_outdoor_mode=False,
        source_reference="India GHG Program / Urban Metro Rail Sustainability Reports (2024)",
        effective_year=2024,
    ),
    ReferenceEmissionFactorSpec(
        category="transport",
        mode_or_region_code="two_wheeler_petrol",
        display_label="Petrol Two-Wheeler",
        factor_value=0.048,
        unit="kg_co2e_per_vkm",
        default_occupancy=1.0,
        exposure_modifier=1.0,
        is_active_outdoor_mode=True,
        source_reference="India GHG Program — Two-Wheeler Emission Factor (2024)",
        effective_year=2024,
    ),
    ReferenceEmissionFactorSpec(
        category="transport",
        mode_or_region_code="two_wheeler_ev",
        display_label="Electric Two-Wheeler",
        factor_value=0.021,
        unit="kg_co2e_per_vkm",
        default_occupancy=1.0,
        exposure_modifier=1.0,
        is_active_outdoor_mode=True,
        source_reference="IEA / India Grid-Adjusted Electric Two-Wheeler Factor (2024)",
        effective_year=2024,
    ),
    ReferenceEmissionFactorSpec(
        category="transport",
        mode_or_region_code="bicycle",
        display_label="Bicycle",
        factor_value=0.0,
        unit="kg_co2e_per_pkm",
        default_occupancy=1.0,
        exposure_modifier=1.15,
        is_active_outdoor_mode=True,
        source_reference="IPCC Zero Direct Tailpipe Mobility Reference (2024)",
        effective_year=2024,
    ),
    ReferenceEmissionFactorSpec(
        category="transport",
        mode_or_region_code="walk",
        display_label="Walking",
        factor_value=0.0,
        unit="kg_co2e_per_pkm",
        default_occupancy=1.0,
        exposure_modifier=1.05,
        is_active_outdoor_mode=True,
        source_reference="IPCC Zero Direct Tailpipe Mobility Reference (2024)",
        effective_year=2024,
    ),
    ReferenceEmissionFactorSpec(
        category="transport",
        mode_or_region_code="work_from_home",
        display_label="Work from Home (Avoided Commute)",
        factor_value=0.0,
        unit="kg_co2e_per_pkm",
        default_occupancy=1.0,
        exposure_modifier=0.30,
        is_active_outdoor_mode=False,
        source_reference="Avoided Passenger Commute Baseline Reference (2024)",
        effective_year=2024,
    ),
    ReferenceEmissionFactorSpec(
        category="electricity_grid",
        mode_or_region_code="india_cea_grid_avg",
        display_label="India National Grid Average (CEA)",
        factor_value=0.716,
        unit="kg_co2e_per_kwh",
        default_occupancy=None,
        exposure_modifier=None,
        is_active_outdoor_mode=False,
        source_reference="Central Electricity Authority (CEA) CO2 Baseline Database v19 (2024)",
        effective_year=2024,
    ),
    ReferenceEmissionFactorSpec(
        category="electricity_grid",
        mode_or_region_code="us_epa_egrid_avg",
        display_label="US EPA eGRID National Average",
        factor_value=0.386,
        unit="kg_co2e_per_kwh",
        default_occupancy=None,
        exposure_modifier=None,
        is_active_outdoor_mode=False,
        source_reference="US EPA eGRID Summary Tables (2024)",
        effective_year=2024,
    ),
)

REFERENCE_FACTORS_BY_CODE: dict[str, ReferenceEmissionFactorSpec] = {
    spec.mode_or_region_code: spec for spec in REFERENCE_EMISSION_FACTORS
}
