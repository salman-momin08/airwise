from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.services.air_quality.aqi_calculator import AQIStandard, PollutantCode


class PollutantReadingSchema(BaseModel):
    pollutant: PollutantCode
    concentration: float = Field(ge=0)
    unit: str
    averaging_period_hours: int = Field(ge=1)
    sub_index: int | None = None


class CurrentAirQualitySchema(BaseModel):
    city: str
    location_precision: Literal["city", "postal_code", "neighborhood", "exact"] = "city"
    standard: AQIStandard
    status: Literal["available", "unavailable"]
    aqi: int | None = None
    category: str | None = None
    dominant_pollutant: PollutantCode | None = None
    pollutants: list[PollutantReadingSchema] = Field(default_factory=list)
    measured_at: datetime | None = None
    provider: str
    source_type: Literal["station", "model", "unavailable"]
    is_stale: bool = False
    is_development_fixture: bool = False
    precaution_summary: str
    unavailable_reason: str | None = None
