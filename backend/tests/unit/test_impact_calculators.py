from __future__ import annotations

import unittest

import pytest

from app.services.impact.calculators import (
    calculate_household_energy_emissions,
    calculate_indoor_filtration_ach,
    calculate_transport_emissions,
    estimate_relative_exposure_change,
)


class TestDeterministicImpactCalculators(unittest.TestCase):
    def test_transport_emissions_accounts_for_vehicle_occupancy(self) -> None:
        # Solo car (0.18 kg/vkm, occ 1) vs 3-person carpool (0.18 kg/vkm, occ 3) over 20 km
        res = calculate_transport_emissions(
            distance_km=20.0,
            baseline_vkm_factor_kg_co2e=0.18,
            baseline_occupancy=1.0,
            alternative_vkm_factor_kg_co2e=0.18,
            alternative_occupancy=3.0,
            factor_source_reference="Test Reference Factor",
        )
        assert res.is_estimate
        assert res.baseline_value == 3.6
        assert res.alternative_value == 1.2
        assert res.estimated_difference == 2.4
        assert res.unit == "kg_co2e"

    def test_zero_occupancy_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="occupancy"):
            calculate_transport_emissions(
                distance_km=10.0,
                baseline_vkm_factor_kg_co2e=0.15,
                baseline_occupancy=0.0,
                alternative_vkm_factor_kg_co2e=0.03,
                alternative_occupancy=1.0,
                factor_source_reference="Ref",
            )

    def test_household_energy_and_filtration_calculators(self) -> None:
        energy = calculate_household_energy_emissions(
            baseline_power_kw=2.0,
            alternative_power_kw=1.2,
            operating_hours=5.0,
            grid_emission_factor_kg_per_kwh=0.71,
            grid_source_reference="CEA India Baseline Grid Factor",
        )
        # Baseline = 10 kWh * 0.71 = 7.1 kg; Alt = 6 kWh * 0.71 = 4.26 kg; Diff = 2.84 kg
        assert energy.baseline_value == 7.1
        assert energy.alternative_value == 4.26
        assert energy.estimated_difference == 2.84

        ach = calculate_indoor_filtration_ach(
            room_area_m2=20.0,
            ceiling_height_m=3.0,
            cadr_m3_per_hour=300.0,
        )
        assert ach.alternative_value == 5.0
        assert ach.unit == "clean_air_changes_per_hour"

    def test_relative_exposure_change(self) -> None:
        exp = estimate_relative_exposure_change(
            outdoor_pm25_ug_m3=180.0,
            duration_hours=1.0,
            baseline_env_modifier=1.0,
            alternative_env_modifier=0.35,
            assumption_note="Outdoor walk vs filtered indoor exercise",
        )
        assert exp.baseline_value == 180.0
        assert exp.alternative_value == 63.0
        assert exp.estimated_difference == 117.0


if __name__ == "__main__":
    unittest.main()
