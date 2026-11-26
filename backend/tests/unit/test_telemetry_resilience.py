from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.config import Settings
from app.core.exceptions import ExternalProviderUnavailableError
from app.integrations.air_quality.provider import (
    FailoverAirQualityClient,
    NormalizedForecastPayload,
    NormalizedHistoryPayload,
    NormalizedProviderPayload,
    NormalizedStationTelemetry,
)
from app.integrations.http_resilience import (
    ProviderCircuitBreaker,
    assert_allowed_https_url,
)
from app.services.air_quality.aqi_calculator import (
    AQIStandard,
    PollutantCode,
    calculate_aqi,
    convert_gas_unit_for_standard,
)
from app.services.air_quality.cache import StaleAwareTelemetryCache
from app.services.air_quality.telemetry_service import AirQualityTelemetryService


class _FailingPrimaryAdapter:
    provider_slug = "openaq"

    async def fetch_city_measurements(self, city: str) -> NormalizedProviderPayload:
        raise ExternalProviderUnavailableError(
            code="OPENAQ_TIMEOUT",
            message=f"Primary OpenAQ timed out for {city}.",
        )

    async def fetch_city_stations(self, city: str) -> list[NormalizedStationTelemetry]:
        raise ExternalProviderUnavailableError()

    async def fetch_city_forecast(
        self, city: str, hours: int = 24
    ) -> NormalizedForecastPayload:
        raise ExternalProviderUnavailableError()

    async def fetch_city_history(
        self, city: str, period: Literal["24h", "7d", "30d"]
    ) -> NormalizedHistoryPayload:
        raise ExternalProviderUnavailableError()


class _ToggleableFallbackAdapter:
    provider_slug = "openweather"

    def __init__(self) -> None:
        self.should_fail = False

    async def fetch_city_measurements(self, city: str) -> NormalizedProviderPayload:
        if self.should_fail:
            raise ExternalProviderUnavailableError(
                code="OPENWEATHER_DOWN",
                message="Fallback OpenWeather is unreachable.",
            )
        return NormalizedProviderPayload(
            city=city.title(),
            provider="openweather",
            source_type="model",
            measured_at=datetime.now(tz=UTC),
            is_stale=False,
            is_development_fixture=False,
            measurements={
                PollutantCode.PM25: (145.0, "ug/m3"),
                PollutantCode.PM10: (240.0, "ug/m3"),
                PollutantCode.NO2: (68.0, "ug/m3"),
                PollutantCode.CO: (1.4, "mg/m3"),
            },
        )

    async def fetch_city_stations(self, city: str) -> list[NormalizedStationTelemetry]:
        return []

    async def fetch_city_forecast(
        self, city: str, hours: int = 24
    ) -> NormalizedForecastPayload:
        raise ExternalProviderUnavailableError()

    async def fetch_city_history(
        self, city: str, period: Literal["24h", "7d", "30d"]
    ) -> NormalizedHistoryPayload:
        raise ExternalProviderUnavailableError()


def test_us_epa_gaseous_breakpoints_and_explicit_unit_conversion() -> None:
    # Convert 76 ug/m3 NO2 -> ppb at 25°C, 1 atm (~40.4 ppb -> Good in US EPA)
    converted_no2 = convert_gas_unit_for_standard(
        PollutantCode.NO2, 76.0, "ug/m3", AQIStandard.US_EPA
    )
    assert converted_no2 is not None
    assert converted_no2[1] == "ppb"
    assert 39.0 <= converted_no2[0] <= 42.0

    # PM2.5 in ppb must never convert
    assert (
        convert_gas_unit_for_standard(
            PollutantCode.PM25, 45.0, "ppb", AQIStandard.INDIA_NAQI
        )
        is None
    )

    # Direct US EPA O3 0.075 ppm -> Unhealthy for Sensitive Groups
    epa_o3 = calculate_aqi(
        AQIStandard.US_EPA,
        {PollutantCode.O3: (0.075, "ppm")},
    )
    assert epa_o3.status == "available"
    assert epa_o3.category == "Unhealthy for Sensitive Groups"


def test_ssrf_host_allowlist_blocks_untrusted_targets() -> None:
    assert_allowed_https_url("https://api.openaq.org/v3/locations")
    with pytest.raises(ExternalProviderUnavailableError):
        assert_allowed_https_url("http://169.254.169.254/latest/meta-data/")
    with pytest.raises(ExternalProviderUnavailableError):
        assert_allowed_https_url("https://evil.example.org/v3/locations")


async def test_primary_to_fallback_failover_and_stale_cache_warning(
    db_engine: AsyncEngine,
) -> None:
    primary_breaker = ProviderCircuitBreaker("openaq", failure_threshold=2)
    fallback_adapter = _ToggleableFallbackAdapter()
    failover_client = FailoverAirQualityClient(
        primary=_FailingPrimaryAdapter(),
        fallback=fallback_adapter,
        primary_breaker=primary_breaker,
    )
    cache = StaleAwareTelemetryCache()
    settings = Settings(app_env="test")

    session_factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)
    async with session_factory() as session:
        service = AirQualityTelemetryService(
            session=session,
            settings=settings,
            adapter_client=failover_client,
            cache=cache,
        )

        # 1. Primary fails -> falls over cleanly to secondary (modeled)
        reading = await service.get_current_air_quality(
            city="Delhi", standard=AQIStandard.INDIA_NAQI
        )
        assert reading.provider == "openweather"
        assert reading.source_type == "model"
        assert reading.is_stale is False
        assert reading.aqi is not None and reading.aqi > 300

        # Second failure trips primary circuit breaker to "open"
        cache_key = "aqi:current:india_naqi:delhi"
        cache.expire_fresh_for_testing(cache_key)
        await service.get_current_air_quality(
            city="Delhi", standard=AQIStandard.INDIA_NAQI
        )
        assert primary_breaker.state == "open"

        # 2. Expire fresh TTL and take fallback offline -> serves stale backup with is_stale=True
        cache.expire_fresh_for_testing(cache_key)
        fallback_adapter.should_fail = True
        stale_reading = await service.get_current_air_quality(
            city="Delhi", standard=AQIStandard.INDIA_NAQI
        )
        assert stale_reading.is_stale is True
        assert stale_reading.aqi == reading.aqi

        # 3. Uncached city when all providers are down -> raises 503 (never fabricates numbers)
        with pytest.raises(ExternalProviderUnavailableError):
            await service.get_current_air_quality(
                city="Mumbai", standard=AQIStandard.INDIA_NAQI
            )
