from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import httpx
import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.config import Settings
from app.core.exceptions import ExternalProviderUnavailableError
from app.integrations.air_quality.provider import (
    FailoverAirQualityClient,
    NormalizedForecastPayload,
    NormalizedHistoryPayload,
    NormalizedProviderPayload,
    NormalizedStationTelemetry,
    OpenAQAirQualityAdapter,
    OpenMeteoAirQualityAdapter,
    resolve_air_quality_adapter,
)
from app.integrations.http_resilience import (
    ProviderCircuitBreaker,
    assert_allowed_https_url,
    fetch_json_with_resilience,
)
from app.repositories.telemetry_repository import TelemetryRepository
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


async def test_openaq_v3_resolves_location_latest_by_sensors_id() -> None:
    now_iso = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v3/locations":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": 8118,
                            "name": "ITO Delhi CPCB",
                            "coordinates": {"latitude": 28.6286, "longitude": 77.2410},
                            "datetimeLast": {"utc": now_iso},
                            "sensors": [
                                {"id": 101, "parameter": {"name": "pm25", "units": "µg/m³"}},
                                {"id": 102, "parameter": {"name": "pm10", "units": "µg/m³"}},
                                {"id": 103, "parameter": {"name": "no2", "units": "µg/m³"}},
                            ],
                        }
                    ]
                },
            )
        if request.url.path == "/v3/locations/8118/latest":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"sensorsId": 101, "value": 168.4, "datetime": {"utc": now_iso}},
                        {"sensorsId": 102, "value": 284.0, "datetime": {"utc": now_iso}},
                        {"sensorsId": 103, "value": 72.5, "datetime": {"utc": now_iso}},
                    ]
                },
            )
        return httpx.Response(404)

    adapter = OpenAQAirQualityAdapter(
        api_key="test-openaq-key",
        transport=httpx.MockTransport(respond),
    )
    payload = await adapter.fetch_city_measurements("Delhi")
    assert payload.provider == "openaq"
    assert payload.source_type == "station"
    assert payload.measurements[PollutantCode.PM25] == (168.4, "ug/m3")
    assert payload.measurements[PollutantCode.PM10] == (284.0, "ug/m3")
    assert payload.measurements[PollutantCode.NO2] == (72.5, "ug/m3")


async def test_openaq_does_not_leak_key_to_openweather_and_uses_open_meteo_fallback() -> None:
    settings = Settings(
        app_env="test",
        air_quality_provider="openaq",
        air_quality_fallback_provider="openweather",
        air_quality_api_key="openaq-only-key-not-for-openweather",
    )
    client = resolve_air_quality_adapter(settings)
    assert isinstance(client.fallback, OpenMeteoAirQualityAdapter)

    now_epoch = int(datetime.now(tz=UTC).timestamp())
    meteo_adapter = OpenMeteoAirQualityAdapter(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "current": {
                        "time": now_epoch,
                        "pm2_5": 142.0,
                        "pm10": 230.0,
                        "nitrogen_dioxide": 64.0,
                        "sulphur_dioxide": 18.0,
                        "ozone": 38.0,
                        "carbon_monoxide": 1600.0,
                    }
                },
            )
        )
    )
    res = await meteo_adapter.fetch_city_measurements("Delhi")
    assert res.provider == "open_meteo"
    assert res.source_type == "model"
    assert res.is_development_fixture is False
    assert res.measurements[PollutantCode.CO] == (1.6, "mg/m3")

    calls = 0

    def unauthorized(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, json={"message": "Invalid API key"})

    with pytest.raises(ExternalProviderUnavailableError):
        await fetch_json_with_resilience(
            "https://api.openweathermap.org/data/2.5/air_pollution",
            transport=httpx.MockTransport(unauthorized),
        )
    assert calls == 1


async def test_list_stations_in_bbox_batches_queries_without_n_plus_one(
    db_engine: AsyncEngine,
) -> None:
    now = datetime.now(tz=UTC)
    older = now - timedelta(hours=2)
    session_factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)

    async with session_factory() as session:
        repo = TelemetryRepository(session)
        for idx in range(5):
            for ts, pm25_val in ((older, 90.0 + idx), (now, 180.0 + idx)):
                await repo.upsert_station_with_measurements(
                    NormalizedStationTelemetry(
                        external_station_id=f"delhi-st-{idx}",
                        name=f"Delhi Station {idx}",
                        city="Delhi",
                        state_region="NCT of Delhi",
                        country_code="IN",
                        latitude=28.60 + idx * 0.01,
                        longitude=77.20 + idx * 0.01,
                        provider="openaq",
                        source_type="station",
                        measured_at=ts,
                        is_stale=False,
                        is_development_fixture=False,
                        measurements={
                            PollutantCode.PM25: (pm25_val, "ug/m3"),
                            PollutantCode.PM10: (260.0 + idx, "ug/m3"),
                            PollutantCode.NO2: (55.0, "ug/m3"),
                        },
                    )
                )
        await session.commit()

    select_statements: list[str] = []

    def _count_selects(
        _conn: Any,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        _context: Any,
        _executemany: Any,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            select_statements.append(statement)

    event.listen(db_engine.sync_engine, "before_cursor_execute", _count_selects)
    try:
        async with session_factory() as read_session:
            read_repo = TelemetryRepository(read_session)
            stations = await read_repo.list_stations_in_bbox(
                min_lon=77.0,
                min_lat=28.5,
                max_lon=77.5,
                max_lat=28.8,
            )
    finally:
        event.remove(db_engine.sync_engine, "before_cursor_execute", _count_selects)

    assert len(stations) == 5
    # Constant 2 SELECT queries regardless of station count (1 stations query + 1 batched join)
    assert len(select_statements) == 2
    by_ext_id = {st.external_station_id: meas for st, _, meas, _, _ in stations}
    assert by_ext_id["delhi-st-0"][PollutantCode.PM25] == (180.0, "ug/m3")
    assert by_ext_id["delhi-st-4"][PollutantCode.PM25] == (184.0, "ug/m3")


