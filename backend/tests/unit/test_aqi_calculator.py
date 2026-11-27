from __future__ import annotations

import unittest

from app.services.air_quality.aqi_calculator import (
    AQIStandard,
    PollutantCode,
    calculate_aqi,
)

class TestAQICalculatorStandardsIsolation(unittest.TestCase):
    def test_india_naqi_requires_three_pollutants_including_pm(self) -> None:
        only_two = {
            PollutantCode.PM25: (120.0, "ug/m3"),
            PollutantCode.NO2: (60.0, "ug/m3"),
        }
        result = calculate_aqi(AQIStandard.INDIA_NAQI, only_two)
        self.assertEqual(result.status, "unavailable")
        self.assertIsNone(result.aqi)
        self.assertIn("at least 3 valid pollutants", result.unavailable_reason or "")

    def test_india_naqi_without_pm_returns_unavailable(self) -> None:
        no_pm = {
            PollutantCode.NO2: (50.0, "ug/m3"),
            PollutantCode.SO2: (20.0, "ug/m3"),
            PollutantCode.O3: (40.0, "ug/m3"),
        }
        result = calculate_aqi(AQIStandard.INDIA_NAQI, no_pm)
        self.assertEqual(result.status, "unavailable")
        self.assertIsNone(result.aqi)

    def test_same_pm25_concentration_yields_distinct_standard_results(self) -> None:
        # 90 ug/m3 PM2.5 = top of Moderate (200) in India NAQI, but Unhealthy (~174) in US EPA 2024
        readings = {
            PollutantCode.PM25: (90.0, "ug/m3"),
            PollutantCode.PM10: (100.0, "ug/m3"),
            PollutantCode.NO2: (40.0, "ug/m3"),
        }
        india_res = calculate_aqi(AQIStandard.INDIA_NAQI, readings)
        epa_res = calculate_aqi(AQIStandard.US_EPA, readings)

        self.assertEqual(india_res.status, "available")
        self.assertEqual(india_res.aqi, 200)
        self.assertEqual(india_res.category, "Moderate")
        self.assertEqual(india_res.dominant_pollutant, PollutantCode.PM25)

        self.assertEqual(epa_res.status, "available")
        self.assertEqual(epa_res.aqi, 175)
        self.assertEqual(epa_res.category, "Unhealthy")
        self.assertNotEqual(india_res.category, epa_res.category)

    def test_incompatible_units_are_never_silently_mixed(self) -> None:
        wrong_unit = {PollutantCode.PM25: (50.0, "ppb")}
        epa_res = calculate_aqi(AQIStandard.US_EPA, wrong_unit)
        self.assertEqual(epa_res.status, "unavailable")
        self.assertIsNone(epa_res.aqi)

if __name__ == "__main__":
    unittest.main()
