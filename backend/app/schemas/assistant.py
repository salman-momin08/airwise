"""Pydantic v2 DTOs for Copilot chat turns, structured guidance cards, and verified citations."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.air_quality import CurrentAirQualitySchema
from app.services.air_quality.aqi_calculator import AQIStandard
from app.services.impact.calculators import ImpactResult

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1200)]
ToolName = Literal[
    "get_current_air_quality",
    "get_air_quality_forecast",
    "get_historical_air_quality",
    "get_weather_conditions",
    "get_user_preferences",
    "get_saved_locations",
    "retrieve_environmental_guidelines",
    "calculate_transport_emissions",
    "estimate_exposure_change",
    "compare_daily_routines",
    "generate_sustainable_alternatives",
    "get_community_initiatives",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class TransportCalculation(StrictModel):
    kind: Literal["transport"]
    distance_km: float = Field(ge=0, le=10000)
    baseline_vkm_factor_kg_co2e: float = Field(ge=0, le=100)
    baseline_occupancy: float = Field(gt=0, le=1000)
    alternative_vkm_factor_kg_co2e: float = Field(ge=0, le=100)
    alternative_occupancy: float = Field(gt=0, le=1000)
    factor_source_reference: str = Field(min_length=3, max_length=300)


class ExposureCalculation(StrictModel):
    kind: Literal["exposure"]
    outdoor_pm25_ug_m3: float = Field(ge=0, le=10000)
    duration_hours: float = Field(ge=0, le=24)
    baseline_env_modifier: float = Field(ge=0, le=10)
    alternative_env_modifier: float = Field(ge=0, le=10)
    assumption_note: str = Field(min_length=3, max_length=300)


class ChatRequest(StrictModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: UUID | None = None
    city: str | None = Field(default=None, min_length=2, max_length=100, pattern=r"^[\w .'-]+$")
    standard: AQIStandard = AQIStandard.INDIA_NAQI
    ai_consent: bool = False
    use_preferences: bool = False
    calculation: (
        Annotated[TransportCalculation | ExposureCalculation, Field(discriminator="kind")] | None
    ) = None


class ToolCall(StrictModel):
    name: ToolName
    period: Literal["24h", "7d", "30d"] = "24h"
    hours: int = Field(default=24, ge=6, le=72)


class ToolPlan(StrictModel):
    calls: list[ToolCall] = Field(default_factory=list, max_length=4)


class GeneratedGuidance(StrictModel):
    situation_summary: ShortText
    recommended_action: ShortText
    why_this_helps: ShortText
    uncertainty_or_limitations: ShortText
    safer_alternative: ShortText | None = None
    evidence_document_ids: list[UUID] = Field(default_factory=list, max_length=6)


class EvidenceReference(StrictModel):
    document_id: UUID
    title: str
    publisher: str
    source_url: str
    last_reviewed_date: datetime
    freshness_note: str | None = None


class EnvironmentalConditions(BaseModel):
    standard: AQIStandard
    status: Literal["available", "unavailable"]
    reading: CurrentAirQualitySchema | None = None
    notice: str


class AssistantGuidance(BaseModel):
    situation_summary: str
    environmental_conditions: EnvironmentalConditions
    recommended_action: str
    why_this_helps: str
    estimated_impact: ImpactResult | None = None
    uncertainty_or_limitations: str
    safer_alternative: str | None = None
    evidence_references: list[EvidenceReference] = Field(default_factory=list)


class GenerationInfo(BaseModel):
    request_id: str
    provider: str
    model_name: str
    prompt_version: str
    token_usage: int
    latency_ms: int
    is_fallback: bool
    fallback_reason: str | None = None


class ChatResult(BaseModel):
    conversation_id: UUID | None
    message_id: UUID | None
    structured_response: AssistantGuidance
    citations: list[EvidenceReference]
    generation: GenerationInfo
    tools_used: list[str]


class ConversationData(BaseModel):
    id: UUID
    created_at: datetime


class MessageData(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str
    structured_response: AssistantGuidance | None
    created_at: datetime
