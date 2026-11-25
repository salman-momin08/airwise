from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CurrentWeatherSchema(BaseModel):
    city: str
    temperature_c: float
    humidity_pct: float = Field(ge=0, le=100)
    wind_speed_mps: float = Field(ge=0)
    wind_direction_deg: int | None = Field(default=None, ge=0, le=360)
    inversion_risk_flag: bool | None = None
    dispersion_note: str
    observed_at: datetime
    provider: str
    is_stale: bool = False
    is_development_fixture: bool = False
