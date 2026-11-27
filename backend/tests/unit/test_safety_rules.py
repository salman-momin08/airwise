from __future__ import annotations

import unittest

from app.ai.guardrails.safety_rules import (
    contains_prohibited_scientific_claim,
    evaluate_environmental_safety,
)
from app.ai.tools.registry import ALLOWLISTED_TOOL_NAMES, MAX_TOOL_CALL_DEPTH
from app.services.air_quality.aqi_calculator import AQIStandard

class TestSafetyRulesAndToolAllowlist(unittest.TestCase):
    def test_severe_smog_blocks_outdoor_cycling_and_exertion(self) -> None:
        gate = evaluate_environmental_safety(
            user_message="Should I cycle 12 km to work today to save carbon?",
            standard=AQIStandard.INDIA_NAQI,
            aqi=365,
        )
        self.assertTrue(gate.block_outdoor_exertion)
        self.assertTrue(gate.block_active_outdoor_commute)
        self.assertFalse(gate.has_urgent_medical_flag)

    def test_urgent_symptoms_trigger_medical_escalation(self) -> None:
        gate = evaluate_environmental_safety(
            user_message="My father has chest pain and difficulty breathing in this smog",
            standard=AQIStandard.INDIA_NAQI,
            aqi=280,
            has_vulnerable_household_member=True,
        )
        self.assertTrue(gate.has_urgent_medical_flag)

    def test_prohibited_claims_detected(self) -> None:
        self.assertTrue(
            contains_prohibited_scientific_claim("Buy an ozone generator for your bedroom.")
        )
        self.assertFalse(
            contains_prohibited_scientific_claim(
                "Use a properly sized HEPA air purifier and keep windows closed during peak smog."
            )
        )

    def test_exact_twelve_allowlisted_tools_registered(self) -> None:
        self.assertEqual(len(ALLOWLISTED_TOOL_NAMES), 12)
        self.assertIn("get_current_air_quality", ALLOWLISTED_TOOL_NAMES)
        self.assertIn("calculate_transport_emissions", ALLOWLISTED_TOOL_NAMES)
        self.assertLessEqual(MAX_TOOL_CALL_DEPTH, 5)

if __name__ == "__main__":
    unittest.main()
