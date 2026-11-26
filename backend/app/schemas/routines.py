from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.impact import ImpactEstimateSchema
from app.services.air_quality.aqi_calculator import AQIStandard

TimeBlockLiteral = Literal["morning", "midday", "afternoon", "evening", "night"]
EnvironmentTypeLiteral = Literal["indoor", "outdoor", "transit"]
RoutineStatusLiteral = Literal["draft", "confirmed", "archived"]
ConfidenceLiteral = Literal["low", "medium", "high"]


class EnvironmentalSnapshotSummarySchema(BaseModel):
    city: str
    standard: AQIStandard
    status: Literal["available", "unavailable"]
    aqi: int | None = None
    category: str | None = None
    pm25_ug_m3: float | None = None
    provider: str
    source_type: str
    measured_at: datetime | None = None
    is_stale: bool = False
    is_development_fixture: bool = False
    inversion_risk_flag: bool = False
    dispersion_note: str | None = None
    ventilation_guidance: str
    indoor_air_disclaimer: str = (
        "Indoor air quality is unmeasured unless a dedicated indoor PM2.5 sensor is connected."
    )


class RoutineActivityInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    time_block: TimeBlockLiteral
    start_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    duration_minutes: int = Field(ge=5, le=480)
    title: str = Field(min_length=2, max_length=200)
    environment_type: EnvironmentTypeLiteral
    safer_alternative: str | None = Field(default=None, max_length=400)


class RoutineActivitySchema(BaseModel):
    id: UUID
    slot_order: int
    time_block: TimeBlockLiteral
    start_time: str
    duration_minutes: int
    title: str
    environment_type: EnvironmentTypeLiteral
    exposure_note: str
    safer_alternative: str | None = None
    explanation: str
    safety_warning: str | None = None
    impact_estimate: ImpactEstimateSchema | None = None
    confidence: ConfidenceLiteral


class GenerateRoutineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    city: str = Field(min_length=2, max_length=100, pattern=r"^[\w .'-]+$")
    standard: AQIStandard = AQIStandard.INDIA_NAQI
    plan_date: date | None = None
    location_id: UUID | None = None
    commute_distance_km: float = Field(default=10.0, ge=0, le=200)


class UpdateRoutineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: RoutineStatusLiteral | None = None
    activities: list[RoutineActivityInput] | None = Field(default=None, min_length=1, max_length=10)


class DailyRoutineSchema(BaseModel):
    id: UUID
    location_id: UUID | None = None
    city: str
    plan_date: date
    aqi_standard: AQIStandard
    status: RoutineStatusLiteral
    environmental_snapshot_at: datetime | None = None
    environmental_summary: EnvironmentalSnapshotSummarySchema | None = None
    activities: list[RoutineActivitySchema]
    requires_explicit_confirmation: bool
    created_at: datetime
    updated_at: datetime


class RoutineWindowOptionSchema(BaseModel):
    time_block: TimeBlockLiteral
    window_label: str
    expected_aqi: int | None = None
    expected_category: str | None = None
    outdoor_exertion_allowed: bool
    recommended_environment: EnvironmentTypeLiteral
    rationale: str


class RoutineComparisonSchema(BaseModel):
    city: str
    standard: AQIStandard
    current_aqi: int | None = None
    is_stale: bool = False
    is_development_fixture: bool = False
    priority_hierarchy_note: str
    windows: list[RoutineWindowOptionSchema]
