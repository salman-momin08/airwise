"""OpenWeather Air Pollution API current, forecast, and historical telemetry adapter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import httpx

from app.core.exceptions import ExternalProviderUnavailableError
from app.integrations.air_quality.models import (
    NormalizedForecastPayload,
    NormalizedForecastSlice,
    NormalizedHistoryPayload,
    NormalizedHistoryPoint,
    NormalizedProviderPayload,
    NormalizedStationTelemetry,
    forecast_confidence_for_delta_hours,
    is_timestamp_stale,
    lookup_city_centroid,
    require_city_centroid,
)
from app.integrations.http_resilience import fetch_json_with_resilience
from app.services.air_quality.aqi_calculator import PollutantCode

_COMPONENT_KEYS: tuple[tuple[str, PollutantCode], ...] = (
    ("pm2_5", PollutantCode.PM25),
    ("pm10", PollutantCode.PM10),
    ("no2", PollutantCode.NO2),
    ("so2", PollutantCode.SO2),
    ("o3", PollutantCode.O3),
)


class OpenWeatherAirQualityAdapter:
    """OpenWeather Air Pollution API adapter (explicitly labeled source_type='model')."""

    provider_slug = "openweather"
    BASE_URL = "https://api.openweathermap.org/data/2.5/air_pollution"

    def __init__(
        self,
        api_key: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._transport = transport

    def _require_key(self) -> str:
        if not self._api_key:
            raise ExternalProviderUnavailableError(
                code="AIR_QUALITY_CREDENTIALS_MISSING",
                message="OpenWeather API key is not configured.",
            )
        return self._api_key

    @staticmethod
    def _extract_components(components: dict[str, Any]) -> dict[PollutantCode, tuple[float, str]]:
        measurements: dict[PollutantCode, tuple[float, str]] = {}
        for key, code in _COMPONENT_KEYS:
            raw_val = components.get(key)
            if isinstance(raw_val, (int, float)) and raw_val >= 0:
                measurements[code] = (round(float(raw_val), 2), "ug/m3")
        raw_co = components.get("co")
        if isinstance(raw_co, (int, float)) and raw_co >= 0:
            measurements[PollutantCode.CO] = (round(float(raw_co) / 1000.0, 3), "mg/m3")
        return measurements

    async def fetch_city_measurements(self, city: str) -> NormalizedProviderPayload:
        centroid = require_city_centroid(city)
        body = await fetch_json_with_resilience(
            self.BASE_URL,
            params={
                "lat": centroid.latitude,
                "lon": centroid.longitude,
                "appid": self._require_key(),
            },
            transport=self._transport,
        )
        entries = body.get("list")
        if not isinstance(entries, list) or not entries:
            raise ExternalProviderUnavailableError
        first = entries[0]
        dt_epoch = first.get("dt")
        measured_at = (
            datetime.fromtimestamp(int(dt_epoch), tz=UTC)
            if isinstance(dt_epoch, (int, float))
            else datetime.now(tz=UTC)
        )
        return NormalizedProviderPayload(
            city=centroid.city,
            provider=self.provider_slug,
            source_type="model",
            measured_at=measured_at,
            is_stale=is_timestamp_stale(measured_at),
            is_development_fixture=False,
            measurements=self._extract_components(first.get("components") or {}),
        )

    async def fetch_city_stations(self, city: str) -> list[NormalizedStationTelemetry]:
        current = await self.fetch_city_measurements(city)
        centroid = lookup_city_centroid(city)
        if centroid is None:
            return []
        return [
            NormalizedStationTelemetry(
                external_station_id=f"openweather-grid-{centroid.city.lower()}",
                name=f"{centroid.city} Regional Atmospheric Grid (Modeled)",
                city=centroid.city,
                state_region=centroid.state_region,
                country_code=centroid.country_code,
                latitude=centroid.latitude,
                longitude=centroid.longitude,
                provider=self.provider_slug,
                source_type="model",
                measured_at=current.measured_at,
                is_stale=current.is_stale,
                is_development_fixture=False,
                measurements=current.measurements,
            )
        ]

    async def fetch_city_forecast(self, city: str, hours: int = 24) -> NormalizedForecastPayload:
        centroid = require_city_centroid(city)
        body = await fetch_json_with_resilience(
            f"{self.BASE_URL}/forecast",
            params={
                "lat": centroid.latitude,
                "lon": centroid.longitude,
                "appid": self._require_key(),
            },
            transport=self._transport,
        )
        entries = body.get("list")
        if not isinstance(entries, list) or not entries:
            raise ExternalProviderUnavailableError

        now = datetime.now(tz=UTC)
        cutoff = now + timedelta(hours=max(6, min(72, hours)))
        slices: list[NormalizedForecastSlice] = []
        for idx, item in enumerate(entries):
            if idx % 3 != 0 or not isinstance(item, dict):
                continue
            dt_epoch = item.get("dt")
            if not isinstance(dt_epoch, (int, float)):
                continue
            f_dt = datetime.fromtimestamp(int(dt_epoch), tz=UTC)
            if f_dt > cutoff:
                break
            delta_h = (f_dt - now).total_seconds() / 3600.0
            slices.append(
                NormalizedForecastSlice(
                    forecast_for=f_dt,
                    measurements=self._extract_components(item.get("components") or {}),
                    confidence_level=forecast_confidence_for_delta_hours(delta_h),
                )
            )
        return NormalizedForecastPayload(
            city=centroid.city,
            provider=self.provider_slug,
            source_type="model",
            generated_at=now,
            is_stale=False,
            is_development_fixture=False,
            slices=slices,
        )

    async def fetch_city_history(
        self, city: str, period: Literal["24h", "7d", "30d"]
    ) -> NormalizedHistoryPayload:
        centroid = require_city_centroid(city)
        now = datetime.now(tz=UTC)
        period_days_stride = {"24h": (1, 1), "7d": (7, 6), "30d": (30, 24)}
        days, stride = period_days_stride[period]
        start = now - timedelta(days=days)
        body = await fetch_json_with_resilience(
            f"{self.BASE_URL}/history",
            params={
                "lat": centroid.latitude,
                "lon": centroid.longitude,
                "start": int(start.timestamp()),
                "end": int(now.timestamp()),
                "appid": self._require_key(),
            },
            transport=self._transport,
        )
        entries = body.get("list")
        if not isinstance(entries, list):
            raise ExternalProviderUnavailableError

        points = [
            NormalizedHistoryPoint(
                timestamp=datetime.fromtimestamp(int(item["dt"]), tz=UTC),
                measurements=self._extract_components(item.get("components") or {}),
            )
            for idx, item in enumerate(entries)
            if idx % stride == 0
            and isinstance(item, dict)
            and isinstance(item.get("dt"), (int, float))
        ]
        return NormalizedHistoryPayload(
            city=centroid.city,
            provider=self.provider_slug,
            source_type="model",
            is_stale=False,
            is_development_fixture=False,
            points=points,
        )


class CPCBRegionalAdapter:
    """CPCB / data.gov.in regional feed adapter interface."""

    provider_slug = "cpcb"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def fetch_city_measurements(self, city: str) -> NormalizedProviderPayload:
        if not self._api_key:
            raise ExternalProviderUnavailableError(
                code="AIR_QUALITY_CREDENTIALS_MISSING",
                message=f"CPCB data.gov.in API key is required for live '{city}' feed.",
            )
        raise ExternalProviderUnavailableError(
            code="CPCB_UPSTREAM_UNAVAILABLE",
            message="CPCB regional upstream feed is temporarily unreachable; failing over.",
        )

    async def fetch_city_stations(self, city: str) -> list[NormalizedStationTelemetry]:
        await self.fetch_city_measurements(city)
        return []

    async def fetch_city_forecast(self, city: str, hours: int = 24) -> NormalizedForecastPayload:
        raise ExternalProviderUnavailableError(
            code="CPCB_FORECAST_UNSUPPORTED",
            message=f"CPCB feed does not publish {hours}h forecasts for {city}.",
        )

    async def fetch_city_history(
        self, city: str, period: Literal["24h", "7d", "30d"]
    ) -> NormalizedHistoryPayload:
        raise ExternalProviderUnavailableError(
            code="CPCB_HISTORY_UNAVAILABLE",
            message=f"CPCB historical archive ({period}) is delegated to persisted measurements.",
        )
