from __future__ import annotations

from dataclasses import dataclass

from app.services.air_quality.aqi_calculator import AQIStandard

URGENT_SYMPTOM_KEYWORDS: tuple[str, ...] = (
    "chest pain",
    "can't breathe",
    "cannot breathe",
    "difficulty breathing",
    "severe shortness of breath",
    "blue lips",
    "fainting",
)

PROHIBITED_CLAIM_PATTERNS: tuple[str, ...] = (
    "ozone generator",
    "houseplants remove pm2.5",
    "eliminates 100% of exposure",
    "eliminates all exposure",
)


@dataclass(frozen=True)
class SafetyEvaluation:
    has_urgent_medical_flag: bool
    block_outdoor_exertion: bool
    block_active_outdoor_commute: bool
    mandatory_directives: tuple[str, ...]


def evaluate_environmental_safety(
    *,
    user_message: str,
    standard: AQIStandard | None,
    aqi: int | None,
    has_vulnerable_household_member: bool = False,
) -> SafetyEvaluation:
    """Deterministic safety rule gate executed before and alongside LLM synthesis."""
    normalized = user_message.lower()
    urgent = any(symptom in normalized for symptom in URGENT_SYMPTOM_KEYWORDS)
    directives: list[str] = []

    if urgent:
        directives.append(
            "User described potential acute symptoms: advise urgent professional medical "
            "evaluation immediately and do not provide clinical diagnosis."
        )

    block_exertion = False
    block_active_commute = False

    if aqi is not None and standard is not None:
        severe_threshold = 301 if standard == AQIStandard.INDIA_NAQI else 201
        poor_threshold = 201 if standard == AQIStandard.INDIA_NAQI else 151
        sensitive_threshold = 101

        if aqi >= severe_threshold:
            block_exertion = True
            block_active_commute = True
            directives.append(
                f"Pollution is Very Poor/Severe ({standard.value}={aqi}): prioritize indoor "
                "exposure reduction; never recommend outdoor cycling, walking commutes, "
                "or outdoor exercise."
            )
        elif aqi >= poor_threshold:
            block_exertion = True
            block_active_commute = has_vulnerable_household_member
            directives.append(
                f"Pollution is Poor/Unhealthy ({standard.value}={aqi}): avoid prolonged "
                "outdoor exertion and prioritize enclosed low-emission transit over "
                "roadside cycling."
            )
        elif aqi >= sensitive_threshold and has_vulnerable_household_member:
            block_exertion = True
            directives.append(
                "Household includes vulnerable members under elevated pollution: apply "
                "conservative outdoor duration limits."
            )
    else:
        directives.append(
            "Live verified AQI is unavailable: state unavailability explicitly and do not "
            "invent local pollution numbers."
        )

    return SafetyEvaluation(
        has_urgent_medical_flag=urgent,
        block_outdoor_exertion=block_exertion,
        block_active_outdoor_commute=block_active_commute,
        mandatory_directives=tuple(directives),
    )


def contains_prohibited_scientific_claim(generated_text: str) -> bool:
    lowered = generated_text.lower()
    return any(pattern in lowered for pattern in PROHIBITED_CLAIM_PATTERNS)
