from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.services.air_quality.aqi_calculator import AQIStandard, PollutantCode

HistoryPeriodLiteral = Literal["24h", "7d", "30d"]
SourceTypeLiteral = Literal["station", "model", "unavailable"]


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
    source_type: SourceTypeLiteral
    is_stale: bool = False
    is_development_fixture: bool = False
    precaution_summary: str
    unavailable_reason: str | None = None


class HistoricalAirQualityPointSchema(BaseModel):
    timestamp: datetime
    aqi: int | None = None
    category: str | None = None
    pm25_ug_m3: float | None = Field(default=None, ge=0)
    pm10_ug_m3: float | None = Field(default=None, ge=0)
    dominant_pollutant: PollutantCode | None = None


class HistoricalAirQualitySchema(BaseModel):
    city: str
    standard: AQIStandard
    period: HistoryPeriodLiteral
    provider: str
    source_type: SourceTypeLiteral
    is_stale: bool = False
    is_development_fixture: bool = False
    series: list[HistoricalAirQualityPointSchema] = Field(default_factory=list)


class ForecastPointSchema(BaseModel):
    forecast_for: datetime
    aqi: int | None = None
    category: str | None = None
    dominant_pollutant: PollutantCode | None = None
    pm25_ug_m3: float | None = Field(default=None, ge=0)
    pm10_ug_m3: float | None = Field(default=None, ge=0)
    confidence_level: Literal["low", "medium", "high"] = "medium"
    safer_outdoor_window: bool = False


class AirQualityForecastSchema(BaseModel):
    city: str
    standard: AQIStandard
    generated_at: datetime
    provider: str
    source_type: SourceTypeLiteral
    is_stale: bool = False
    is_development_fixture: bool = False
    points: list[ForecastPointSchema] = Field(default_factory=list)


class MonitoringStationSchema(BaseModel):
    station_id: str
    name: str
    city: str
    state_region: str | None = None
    country_code: str = "IN"
    latitude: float
    longitude: float
    distance_km: float | None = None
    provider: str
    source_type: Literal["station", "model"]
    standard: AQIStandard
    aqi: int | None = None
    category: str | None = None
    dominant_pollutant: PollutantCode | None = None
    measured_at: datetime | None = None
    is_stale: bool = False
    is_development_fixture: bool = False


class GeoJsonPointGeometrySchema(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: tuple[float, float]


class StationGeoJsonPropertiesSchema(BaseModel):
    station_id: str
    name: str
    city: str
    provider: str
    source_type: Literal["station", "model"]
    standard: AQIStandard
    aqi: int | None = None
    category: str | None = None
    dominant_pollutant: PollutantCode | None = None
    measured_at: datetime | None = None
    is_stale: bool = False
    is_development_fixture: bool = False


class StationGeoJsonFeatureSchema(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: GeoJsonPointGeometrySchema
    properties: StationGeoJsonPropertiesSchema


class StationGeoJsonCollectionSchema(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    standard: AQIStandard
    is_development_fixture: bool = False
    features: list[StationGeoJsonFeatureSchema] = Field(default_factory=list)
