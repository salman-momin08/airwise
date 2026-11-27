"""OpenWeather, Open-Meteo, and labeled fixture weather adapters with inversion heuristics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar, Protocol

import httpx

from app.core.config import Settings
from app.core.exceptions import ExternalProviderUnavailableError
from app.integrations.air_quality.provider import (
    is_timestamp_stale,
    lookup_city_centroid,
)
from app.integrations.http_resilience import (
    ProviderCircuitBreaker,
    fetch_json_with_resilience,
)


def evaluate_inversion_stagnation_risk(
    *, temperature_c: float, humidity_pct: float, wind_speed_mps: float
) -> bool:
    """Deterministic indicator for cool, humid, calm winter boundary-layer stagnation."""
    return wind_speed_mps < 2.2 and temperature_c <= 19.0 and humidity_pct >= 62.0


@dataclass(frozen=True)
class NormalizedWeatherPayload:
    city: str
    latitude: float
    longitude: float
    temperature_c: float
    humidity_pct: float
    wind_speed_mps: float
    wind_direction_deg: int | None
    inversion_risk_flag: bool
    observed_at: datetime
    provider: str
    is_stale: bool
    is_development_fixture: bool


class WeatherProviderAdapter(Protocol):
    provider_slug: str

    async def fetch_city_weather(self, city: str) -> NormalizedWeatherPayload: ...


class DevelopmentFixtureWeatherAdapter:
    """Explicitly labeled development weather fixture (blocked in APP_ENV=production)."""

    provider_slug = "development_fixture"

    FIXTURE_METEOROLOGY: ClassVar[dict[str, tuple[float, float, float, int]]] = {
        "delhi": (15.4, 74.0, 1.3, 290),
        "gurugram": (16.1, 70.0, 1.5, 285),
        "noida": (15.8, 72.0, 1.4, 295),
        "bengaluru": (24.2, 58.0, 3.8, 110),
        "mumbai": (28.5, 68.0, 3.4, 250),
        "chennai": (27.9, 76.0, 4.2, 95),
        "kolkata": (19.6, 71.0, 1.9, 320),
        "hyderabad": (25.1, 52.0, 3.1, 130),
        "pune": (23.4, 54.0, 2.9, 260),
        "lucknow": (16.5, 73.0, 1.6, 300),
    }

    async def fetch_city_weather(self, city: str) -> NormalizedWeatherPayload:
        centroid = lookup_city_centroid(city)
        met = self.FIXTURE_METEOROLOGY.get(city.strip().lower())
        if centroid is None or met is None:
            raise ExternalProviderUnavailableError(
                code="WEATHER_FIXTURE_CITY_NOT_CONFIGURED",
                message=f"No weather fixture exists for '{city}'.",
            )
        temp_c, humidity, wind_mps, wind_deg = met
        return NormalizedWeatherPayload(
            city=centroid.city,
            latitude=centroid.latitude,
            longitude=centroid.longitude,
            temperature_c=temp_c,
            humidity_pct=humidity,
            wind_speed_mps=wind_mps,
            wind_direction_deg=wind_deg,
            inversion_risk_flag=evaluate_inversion_stagnation_risk(
                temperature_c=temp_c,
                humidity_pct=humidity,
                wind_speed_mps=wind_mps,
            ),
            observed_at=datetime.now(tz=UTC),
            provider=self.provider_slug,
            is_stale=False,
            is_development_fixture=True,
        )


class OpenWeatherCurrentAdapter:
    provider_slug = "openweather"
    BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

    def __init__(
        self,
        api_key: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._transport = transport

    async def fetch_city_weather(self, city: str) -> NormalizedWeatherPayload:
        if not self._api_key:
            raise ExternalProviderUnavailableError(
                code="WEATHER_CREDENTIALS_MISSING",
                message="OpenWeather API key is not configured.",
            )
        centroid = lookup_city_centroid(city)
        if centroid is None:
            raise ExternalProviderUnavailableError(
                code="WEATHER_CITY_UNSUPPORTED",
                message=f"City '{city}' is not in the supported spatial gazetteer.",
            )
        body = await fetch_json_with_resilience(
            self.BASE_URL,
            params={
                "lat": centroid.latitude,
                "lon": centroid.longitude,
                "units": "metric",
                "appid": self._api_key,
            },
            transport=self._transport,
        )
        main = body.get("main") or {}
        wind = body.get("wind") or {}
        temp_c = float(main.get("temp", 22.0))
        humidity = float(main.get("humidity", 55.0))
        wind_mps = float(wind.get("speed", 2.5))
        wind_deg_raw = wind.get("deg")
        wind_deg = int(wind_deg_raw) if isinstance(wind_deg_raw, (int, float)) else None
        dt_epoch = body.get("dt")
        observed_at = (
            datetime.fromtimestamp(int(dt_epoch), tz=UTC)
            if isinstance(dt_epoch, (int, float))
            else datetime.now(tz=UTC)
        )
        return NormalizedWeatherPayload(
            city=centroid.city,
            latitude=centroid.latitude,
            longitude=centroid.longitude,
            temperature_c=round(temp_c, 1),
            humidity_pct=round(humidity, 1),
            wind_speed_mps=round(wind_mps, 2),
            wind_direction_deg=wind_deg,
            inversion_risk_flag=evaluate_inversion_stagnation_risk(
                temperature_c=temp_c,
                humidity_pct=humidity,
                wind_speed_mps=wind_mps,
            ),
            observed_at=observed_at,
            provider=self.provider_slug,
            is_stale=is_timestamp_stale(observed_at),
            is_development_fixture=False,
        )


class OpenMeteoWeatherAdapter:
    """Keyless Open-Meteo adapter for atmospheric dispersion telemetry."""

    provider_slug = "open_meteo"
    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def fetch_city_weather(self, city: str) -> NormalizedWeatherPayload:
        centroid = lookup_city_centroid(city)
        if centroid is None:
            raise ExternalProviderUnavailableError(
                code="WEATHER_CITY_UNSUPPORTED",
                message=f"City '{city}' is not in the supported spatial gazetteer.",
            )
        body = await fetch_json_with_resilience(
            self.BASE_URL,
            params={
                "latitude": centroid.latitude,
                "longitude": centroid.longitude,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m",
                "wind_speed_unit": "ms",
            },
            transport=self._transport,
        )
        current = body.get("current") or {}
        temp_c = float(current.get("temperature_2m", 22.0))
        humidity = float(current.get("relative_humidity_2m", 55.0))
        wind_mps = float(current.get("wind_speed_10m", 2.5))
        wind_deg_raw = current.get("wind_direction_10m")
        wind_deg = int(wind_deg_raw) if isinstance(wind_deg_raw, (int, float)) else None
        return NormalizedWeatherPayload(
            city=centroid.city,
            latitude=centroid.latitude,
            longitude=centroid.longitude,
            temperature_c=round(temp_c, 1),
            humidity_pct=round(humidity, 1),
            wind_speed_mps=round(wind_mps, 2),
            wind_direction_deg=wind_deg,
            inversion_risk_flag=evaluate_inversion_stagnation_risk(
                temperature_c=temp_c,
                humidity_pct=humidity,
                wind_speed_mps=wind_mps,
            ),
            observed_at=datetime.now(tz=UTC),
            provider=self.provider_slug,
            is_stale=False,
            is_development_fixture=False,
        )


class FailoverWeatherClient:
    def __init__(
        self,
        primary: WeatherProviderAdapter,
        fallback: WeatherProviderAdapter | None = None,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.primary_breaker = ProviderCircuitBreaker(f"weather:{primary.provider_slug}")
        self.fallback_breaker = (
            ProviderCircuitBreaker(f"weather:{fallback.provider_slug}")
            if fallback is not None
            else None
        )

    async def fetch_city_weather(self, city: str) -> NormalizedWeatherPayload:
        last_err: ExternalProviderUnavailableError | None = None
        if self.primary_breaker.allow_request():
            try:
                res = await self.primary.fetch_city_weather(city)
                self.primary_breaker.record_success()
                return res
            except ExternalProviderUnavailableError as exc:
                self.primary_breaker.record_failure()
                last_err = exc

        if (
            self.fallback is not None
            and self.fallback_breaker is not None
            and self.fallback_breaker.allow_request()
        ):
            try:
                res = await self.fallback.fetch_city_weather(city)
                self.fallback_breaker.record_success()
                return res
            except ExternalProviderUnavailableError as exc:
                self.fallback_breaker.record_failure()
                last_err = exc

        raise last_err or ExternalProviderUnavailableError(
            code="WEATHER_PROVIDER_UNAVAILABLE",
            message="Current weather telemetry is temporarily unavailable.",
        )


def resolve_weather_adapter(settings: Settings) -> FailoverWeatherClient:
    if settings.weather_provider == "fixture":
        return FailoverWeatherClient(primary=DevelopmentFixtureWeatherAdapter())
    if settings.weather_provider == "openweather":
        return FailoverWeatherClient(
            primary=OpenWeatherCurrentAdapter(api_key=settings.weather_api_key),
            fallback=OpenMeteoWeatherAdapter(),
        )
    return FailoverWeatherClient(primary=OpenMeteoWeatherAdapter())
