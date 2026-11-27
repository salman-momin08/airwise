"""Provider-neutral air quality telemetry models, city centroids, and adapter protocol."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol

from app.core.exceptions import ExternalProviderUnavailableError
from app.services.air_quality.aqi_calculator import PollutantCode

STALE_MEASUREMENT_MAX_AGE_SECONDS = 3 * 3600


@dataclass(frozen=True)
class CityCentroid:
    city: str
    state_region: str
    country_code: str
    latitude: float
    longitude: float
    timezone: str


CITY_COORDINATE_GAZETTEER: dict[str, CityCentroid] = {
    "delhi": CityCentroid("Delhi", "NCT of Delhi", "IN", 28.6139, 77.2090, "Asia/Kolkata"),
    "gurugram": CityCentroid("Gurugram", "Haryana", "IN", 28.4595, 77.0266, "Asia/Kolkata"),
    "noida": CityCentroid("Noida", "Uttar Pradesh", "IN", 28.5355, 77.3910, "Asia/Kolkata"),
    "bengaluru": CityCentroid("Bengaluru", "Karnataka", "IN", 12.9716, 77.5946, "Asia/Kolkata"),
    "mumbai": CityCentroid("Mumbai", "Maharashtra", "IN", 19.0760, 72.8777, "Asia/Kolkata"),
    "chennai": CityCentroid("Chennai", "Tamil Nadu", "IN", 13.0827, 80.2707, "Asia/Kolkata"),
    "kolkata": CityCentroid("Kolkata", "West Bengal", "IN", 22.5726, 88.3639, "Asia/Kolkata"),
    "hyderabad": CityCentroid("Hyderabad", "Telangana", "IN", 17.3850, 78.4867, "Asia/Kolkata"),
    "pune": CityCentroid("Pune", "Maharashtra", "IN", 18.5204, 73.8567, "Asia/Kolkata"),
    "lucknow": CityCentroid("Lucknow", "Uttar Pradesh", "IN", 26.8467, 80.9462, "Asia/Kolkata"),
}


def lookup_city_centroid(city: str) -> CityCentroid | None:
    return CITY_COORDINATE_GAZETTEER.get(city.strip().lower())


def require_city_centroid(city: str) -> CityCentroid:
    centroid = lookup_city_centroid(city)
    if centroid is None:
        raise ExternalProviderUnavailableError(
            code="AIR_QUALITY_CITY_UNSUPPORTED",
            message=f"City '{city}' is not in the supported spatial gazetteer.",
        )
    return centroid


def is_timestamp_stale(measured_at: datetime, now: datetime | None = None) -> bool:
    ref = now or datetime.now(tz=UTC)
    ts = measured_at if measured_at.tzinfo else measured_at.replace(tzinfo=UTC)
    return (ref - ts).total_seconds() > STALE_MEASUREMENT_MAX_AGE_SECONDS


def forecast_confidence_for_delta_hours(
    delta_hours: float,
) -> Literal["low", "medium", "high"]:
    if delta_hours <= 12:
        return "high"
    if delta_hours <= 36:
        return "medium"
    return "low"


@dataclass(frozen=True)
class NormalizedStationTelemetry:
    external_station_id: str
    name: str
    city: str
    state_region: str | None
    country_code: str
    latitude: float
    longitude: float
    provider: str
    source_type: Literal["station", "model"]
    measured_at: datetime
    is_stale: bool
    is_development_fixture: bool
    measurements: dict[PollutantCode, tuple[float, str]]


@dataclass(frozen=True)
class NormalizedProviderPayload:
    city: str
    provider: str
    source_type: Literal["station", "model"]
    measured_at: datetime
    is_stale: bool
    is_development_fixture: bool
    measurements: dict[PollutantCode, tuple[float, str]]


@dataclass(frozen=True)
class NormalizedForecastSlice:
    forecast_for: datetime
    measurements: dict[PollutantCode, tuple[float, str]]
    confidence_level: Literal["low", "medium", "high"]


@dataclass(frozen=True)
class NormalizedForecastPayload:
    city: str
    provider: str
    source_type: Literal["station", "model"]
    generated_at: datetime
    is_stale: bool
    is_development_fixture: bool
    slices: list[NormalizedForecastSlice]


@dataclass(frozen=True)
class NormalizedHistoryPoint:
    timestamp: datetime
    measurements: dict[PollutantCode, tuple[float, str]]


@dataclass(frozen=True)
class NormalizedHistoryPayload:
    city: str
    provider: str
    source_type: Literal["station", "model"]
    is_stale: bool
    is_development_fixture: bool
    points: list[NormalizedHistoryPoint]


class AirQualityProviderAdapter(Protocol):
    provider_slug: str

    async def fetch_city_measurements(self, city: str) -> NormalizedProviderPayload: ...

    async def fetch_city_stations(self, city: str) -> list[NormalizedStationTelemetry]: ...

    async def fetch_city_forecast(
        self, city: str, hours: int = 24
    ) -> NormalizedForecastPayload: ...

    async def fetch_city_history(
        self, city: str, period: Literal["24h", "7d", "30d"]
    ) -> NormalizedHistoryPayload: ...
