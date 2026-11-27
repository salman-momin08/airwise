"""Prompt-injection screening and post-generation numerical/scientific grounding validators."""

from __future__ import annotations

import re
from uuid import UUID

from app.ai.gateway.gemini import OutputValidationError
from app.ai.guardrails.safety_rules import SafetyEvaluation
from app.ai.rag.knowledge import RetrievedEvidence
from app.schemas.assistant import GeneratedGuidance

_PRIVATE_INPUT = re.compile(
    r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}"
    r"|\b[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b"
    r"|(?<!\w)[+-]?\d{1,3}\.\d{3,}\s*[, /]\s*[+-]?\d{1,3}\.\d{3,}"
    r"|(?<!\w)[+-]?\d{1,3}\.\d{4,}\b"
    r"|\b(?:account|user)[ _-]?id\s*[:=]\s*[\w-]+"
    r"|\b(?:\+?\d[\d ()-]{8,}\d)\b"
    r"|\b\d+\s+[\w ]{1,50}\b(?:street|road|avenue|lane|drive|apartment)\b",
    re.IGNORECASE,
)
_INJECTION = re.compile(
    r"ignore.{0,30}(?:instructions|rules|prompt)"
    r"|(?:reveal|print|show|leak).{0,30}(?:secret|api.key|system.prompt)"
    r"|(?:system|developer)\s*:\s*"
    r"|(?:override|bypass).{0,25}(?:safety|policy|rules)",
    re.IGNORECASE | re.DOTALL,
)


def minimize_text(text: str) -> str:
    return _PRIVATE_INPUT.sub("[private detail removed]", text)


def is_injection(text: str) -> bool:
    return bool(_INJECTION.search(text))


def verify_guidance(
    generated: GeneratedGuidance, evidence: list[RetrievedEvidence], safety: SafetyEvaluation
) -> None:
    retrieved: set[UUID] = {item.reference.document_id for item in evidence}
    if not set(generated.evidence_document_ids) <= retrieved:
        raise OutputValidationError("Citation was not retrieved in this turn.")
    if not generated.evidence_document_ids:
        raise OutputValidationError("Guidance must reference retrieved official evidence.")
    prose = " ".join(
        str(value)
        for key, value in generated.model_dump().items()
        if key != "evidence_document_ids" and value is not None
    )
    without_labels = re.sub(r"PM2\.5|PM10|CO2e?|N95|FFP2|HEPA", "", prose, flags=re.IGNORECASE)
    numerical_words = (
        r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
        r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|"
        r"forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|"
        r"half|quarter|twice|percent|percentage)\b"
    )
    if re.search(r"\d|https?://|<[^>]*>|" + numerical_words, without_labels, re.IGNORECASE):
        raise OutputValidationError(
            "Numerical claims, URLs and HTML are only permitted in backend-grounded fields."
        )
    if is_injection(prose):
        raise OutputValidationError("Generated guidance contained instruction override content.")
    lowered = prose.lower()
    unsafe_claims = (
        r"plants?.{0,40}(?:remove|clean|purif|filter)",
        r"(?:use|buy|recommend|install).{0,20}ozone",
        r"(?:eliminate|remove).{0,10}(?:all|every).{0,15}exposure",
        (
            r"(?:purifier|household|your action).{0,60}(?:reduce|lower|drop).{0,20}"
            r"(?:street|city|outdoor|ambient).{0,15}(?:aqi|pollution)"
        ),
        r"indoor (?:air|aqi).{0,20}(?:is safe|is clean|is good|\bmeasured\b)",
        r"(?:cure|prevent|eliminate).{0,30}(?:asthma|cancer|heart disease|all risk)",
    )
    if any(re.search(pattern, lowered) for pattern in unsafe_claims):
        raise OutputValidationError("Unsupported scientific or indoor measurement claim.")
    if safety.block_outdoor_exertion or safety.block_active_outdoor_commute:
        # Under elevated risk, use deterministic advice rather than attempting to
        # distinguish negated unsafe recommendations in arbitrary generated prose.
        raise OutputValidationError("Elevated pollution requires deterministic safety guidance.")
