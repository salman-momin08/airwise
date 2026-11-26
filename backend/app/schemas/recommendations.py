from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assistant import EvidenceReference, StrictModel
from app.schemas.impact import ImpactEstimateSchema
from app.services.air_quality.aqi_calculator import AQIStandard

RecommendationCategoryLiteral = Literal[
    "routine",
    "transport",
    "indoor_air",
    "household_sustainability",
    "community",
]
RecommendationPriorityLiteral = Literal["critical", "high", "medium", "low"]
RecommendationFeedbackStatusLiteral = Literal[
    "helpful",
    "not_relevant",
    "completed",
    "dismissed",
]


class GenerateRecommendationsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    city: str = Field(min_length=2, max_length=100, pattern=r"^[\w .'-]+$")
    standard: AQIStandard = AQIStandard.INDIA_NAQI
    commute_distance_km: float = Field(default=10.0, ge=0, le=200)
    use_ai_phrasing: bool = False
    ai_consent: bool = False


class RecommendationFeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: RecommendationFeedbackStatusLiteral
    note: str | None = Field(default=None, max_length=500)


class RecommendationFeedbackSchema(BaseModel):
    id: UUID
    recommendation_id: UUID
    status: RecommendationFeedbackStatusLiteral
    note: str | None = None
    created_at: datetime


class RecommendationCardSchema(BaseModel):
    id: UUID
    city: str
    aqi_standard: AQIStandard
    category: RecommendationCategoryLiteral
    priority: RecommendationPriorityLiteral
    title: str
    reason: str
    action_steps: list[str]
    safer_alternative: str | None = None
    uncertainty_note: str
    impact_estimate: ImpactEstimateSchema | None = None
    evidence_references: list[EvidenceReference] = Field(default_factory=list)
    is_ai_enriched: bool = False
    latest_feedback: RecommendationFeedbackStatusLiteral | None = None
    valid_until: datetime
    created_at: datetime


class GeneratedCardPhrasing(StrictModel):
    category: RecommendationCategoryLiteral
    reason: str = Field(min_length=12, max_length=500)


class GeneratedRecommendationsBatch(StrictModel):
    cards: list[GeneratedCardPhrasing] = Field(min_length=1, max_length=5)


class ScreenedAlternativeSchema(BaseModel):
    category: Literal["transport", "household_sustainability", "indoor_air"]
    option_code: str
    title: str
    exposure_safe_now: bool
    safety_rationale: str
    estimated_co2e_difference_kg: float | None = None
    assumptions_note: str
