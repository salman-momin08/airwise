from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Literal, TypeVar

from app.core.config import Settings
from app.core.exceptions import ExternalProviderUnavailableError
from app.integrations.air_quality.fixture_adapter import DevelopmentFixtureAirQualityAdapter
from app.integrations.air_quality.models import (
    CITY_COORDINATE_GAZETTEER,
    STALE_MEASUREMENT_MAX_AGE_SECONDS,
    AirQualityProviderAdapter,
    CityCentroid,
    NormalizedForecastPayload,
    NormalizedForecastSlice,
    NormalizedHistoryPayload,
    NormalizedHistoryPoint,
    NormalizedProviderPayload,
    NormalizedStationTelemetry,
    is_timestamp_stale,
    lookup_city_centroid,
)
from app.integrations.air_quality.open_meteo_adapter import OpenMeteoAirQualityAdapter
from app.integrations.air_quality.openaq_adapter import OpenAQAirQualityAdapter
from app.integrations.air_quality.openweather_adapter import (
    CPCBRegionalAdapter,
    OpenWeatherAirQualityAdapter,
)
from app.integrations.http_resilience import ProviderCircuitBreaker

ResultT = TypeVar("ResultT")

__all__ = [
    "CITY_COORDINATE_GAZETTEER",
    "STALE_MEASUREMENT_MAX_AGE_SECONDS",
    "AirQualityProviderAdapter",
    "CPCBRegionalAdapter",
    "CityCentroid",
    "DevelopmentFixtureAirQualityAdapter",
    "FailoverAirQualityClient",
    "NormalizedForecastPayload",
    "NormalizedForecastSlice",
    "NormalizedHistoryPayload",
    "NormalizedHistoryPoint",
    "NormalizedProviderPayload",
    "NormalizedStationTelemetry",
    "OpenAQAirQualityAdapter",
    "OpenMeteoAirQualityAdapter",
    "OpenWeatherAirQualityAdapter",
    "is_timestamp_stale",
    "lookup_city_centroid",
    "reset_air_quality_circuit_breakers",
    "resolve_air_quality_adapter",
]

class FailoverAirQualityClient:
    """Circuit-breaker-protected primary-to-fallback Air Quality adapter orchestrator."""

    def __init__(
        self,
        primary: AirQualityProviderAdapter,
        fallback: AirQualityProviderAdapter | None = None,
        *,
        primary_breaker: ProviderCircuitBreaker | None = None,
        fallback_breaker: ProviderCircuitBreaker | None = None,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.primary_breaker = primary_breaker or ProviderCircuitBreaker(primary.provider_slug)
        self.fallback_breaker = (
            fallback_breaker or ProviderCircuitBreaker(fallback.provider_slug)
            if fallback is not None
            else None
        )

    async def _call_with_breakers(
        self,
        op: Callable[[AirQualityProviderAdapter], Awaitable[ResultT]],
    ) -> ResultT:
        last_error: ExternalProviderUnavailableError | None = None
        if self.primary_breaker.allow_request():
            try:
                res = await op(self.primary)
                self.primary_breaker.record_success()
                return res
            except ExternalProviderUnavailableError as exc:
                self.primary_breaker.record_failure()
                last_error = exc

        if (
            self.fallback is not None
            and self.fallback_breaker is not None
            and self.fallback_breaker.allow_request()
        ):
            try:
                res = await op(self.fallback)
                self.fallback_breaker.record_success()
                return res
            except ExternalProviderUnavailableError as exc:
                self.fallback_breaker.record_failure()
                last_error = exc

        raise last_error or ExternalProviderUnavailableError()

    async def _call_with_delegation(
        self,
        op: Callable[[AirQualityProviderAdapter], Awaitable[ResultT]],
    ) -> ResultT:
        last_error: ExternalProviderUnavailableError | None = None
        try:
            return await op(self.primary)
        except ExternalProviderUnavailableError as exc:
            last_error = exc

        if self.fallback is not None:
            try:
                return await op(self.fallback)
            except ExternalProviderUnavailableError as exc:
                last_error = exc

        raise last_error or ExternalProviderUnavailableError()

    async def fetch_city_measurements(self, city: str) -> NormalizedProviderPayload:
        return await self._call_with_breakers(
            lambda adapter: adapter.fetch_city_measurements(city)
        )

    async def fetch_city_stations(self, city: str) -> list[NormalizedStationTelemetry]:
        return await self._call_with_breakers(lambda adapter: adapter.fetch_city_stations(city))

    async def fetch_city_forecast(
        self, city: str, hours: int = 24
    ) -> NormalizedForecastPayload:
        return await self._call_with_delegation(
            lambda adapter: adapter.fetch_city_forecast(city, hours=hours)
        )

    async def fetch_city_history(
        self, city: str, period: Literal["24h", "7d", "30d"]
    ) -> NormalizedHistoryPayload:
        return await self._call_with_delegation(
            lambda adapter: adapter.fetch_city_history(city, period=period)
        )

_CIRCUIT_BREAKERS: dict[str, ProviderCircuitBreaker] = {
    "openaq": ProviderCircuitBreaker("openaq"),
    "openweather": ProviderCircuitBreaker("openweather"),
    "open_meteo": ProviderCircuitBreaker("open_meteo"),
    "cpcb": ProviderCircuitBreaker("cpcb"),
    "development_fixture": ProviderCircuitBreaker("development_fixture"),
}

def reset_air_quality_circuit_breakers() -> None:
    for breaker in _CIRCUIT_BREAKERS.values():
        breaker.reset()

def _instantiate_single_adapter(
    provider_name: str, api_key: str
) -> AirQualityProviderAdapter | None:
    if provider_name == "fixture":
        return DevelopmentFixtureAirQualityAdapter()
    if provider_name == "openaq":
        return OpenAQAirQualityAdapter(api_key=api_key)
    if provider_name == "openweather":
        return OpenWeatherAirQualityAdapter(api_key=api_key)
    if provider_name == "open_meteo":
        return OpenMeteoAirQualityAdapter()
    if provider_name == "cpcb":
        return CPCBRegionalAdapter(api_key=api_key)
    return None

def _resolve_fallback_adapter(settings: Settings) -> AirQualityProviderAdapter | None:
    fb_name = settings.air_quality_fallback_provider
    if (
        settings.air_quality_provider == "fixture"
        or fb_name == "none"
        or fb_name == settings.air_quality_provider
    ):
        return None
    if fb_name == "open_meteo":
        return OpenMeteoAirQualityAdapter()
    if fb_name == "openweather":
        ow_key = settings.air_quality_fallback_api_key or (
            settings.weather_api_key if settings.weather_provider == "openweather" else ""
        )
        if not ow_key:
            # Never send a primary OpenAQ/CPCB key to OpenWeather; use keyless Open-Meteo model
            return OpenMeteoAirQualityAdapter()
        return OpenWeatherAirQualityAdapter(api_key=ow_key)
    fb_key = settings.air_quality_fallback_api_key or settings.air_quality_api_key
    return _instantiate_single_adapter(fb_name, fb_key)

def resolve_air_quality_adapter(settings: Settings) -> FailoverAirQualityClient:
    primary = _instantiate_single_adapter(
        settings.air_quality_provider, settings.air_quality_api_key
    )
    if primary is None:
        raise ExternalProviderUnavailableError(
            code="AIR_QUALITY_PROVIDER_NOT_INITIALIZED",
            message="Configured primary air quality provider is unsupported.",
        )

    fallback = _resolve_fallback_adapter(settings)

    return FailoverAirQualityClient(
        primary=primary,
        fallback=fallback,
        primary_breaker=_CIRCUIT_BREAKERS[primary.provider_slug],
        fallback_breaker=(
            _CIRCUIT_BREAKERS[fallback.provider_slug] if fallback is not None else None
        ),
    )
