from __future__ import annotations

import math
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

_METEO_KEYS: tuple[tuple[str, PollutantCode], ...] = (
    ("pm2_5", PollutantCode.PM25),
    ("pm10", PollutantCode.PM10),
    ("nitrogen_dioxide", PollutantCode.NO2),
    ("sulphur_dioxide", PollutantCode.SO2),
    ("ozone", PollutantCode.O3),
)
_HOURLY_SERIES_KEYS = (
    "pm2_5",
    "pm10",
    "nitrogen_dioxide",
    "sulphur_dioxide",
    "ozone",
    "carbon_monoxide",
)

class OpenMeteoAirQualityAdapter:
    """Keyless Open-Meteo CAMS atmospheric model adapter (source_type='model')."""

    provider_slug = "open_meteo"
    BASE_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
    POLLUTANT_PARAMS = "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone"

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    @staticmethod
    def _extract_current(current: dict[str, Any]) -> dict[PollutantCode, tuple[float, str]]:
        measurements: dict[PollutantCode, tuple[float, str]] = {}
        for key, code in _METEO_KEYS:
            raw_val = current.get(key)
            if isinstance(raw_val, (int, float)) and raw_val >= 0:
                measurements[code] = (round(float(raw_val), 2), "ug/m3")
        raw_co = current.get("carbon_monoxide")
        if isinstance(raw_co, (int, float)) and raw_co >= 0:
            measurements[PollutantCode.CO] = (round(float(raw_co) / 1000.0, 3), "mg/m3")
        return measurements

    @classmethod
    def _extract_hourly_index(
        cls, hourly: dict[str, Any], idx: int
    ) -> dict[PollutantCode, tuple[float, str]]:
        row = {
            key: series[idx]
            for key in _HOURLY_SERIES_KEYS
            if isinstance((series := hourly.get(key)), list) and idx < len(series)
        }
        return cls._extract_current(row)

    @staticmethod
    def _require_hourly_payload(body: dict[str, Any]) -> tuple[dict[str, Any], list[Any]]:
        hourly = body.get("hourly")
        times = hourly.get("time") if isinstance(hourly, dict) else None
        if not isinstance(hourly, dict) or not isinstance(times, list) or not times:
            raise ExternalProviderUnavailableError()
        return hourly, times

    async def fetch_city_measurements(self, city: str) -> NormalizedProviderPayload:
        centroid = require_city_centroid(city)
        body = await fetch_json_with_resilience(
            self.BASE_URL,
            params={
                "latitude": centroid.latitude,
                "longitude": centroid.longitude,
                "current": self.POLLUTANT_PARAMS,
                "timeformat": "unixtime",
            },
            transport=self._transport,
        )
        current = body.get("current")
        if not isinstance(current, dict):
            raise ExternalProviderUnavailableError()
        measurements = self._extract_current(current)
        if not measurements:
            raise ExternalProviderUnavailableError()
        raw_ts = current.get("time")
        measured_at = (
            datetime.fromtimestamp(int(raw_ts), tz=UTC)
            if isinstance(raw_ts, (int, float))
            else datetime.now(tz=UTC)
        )
        return NormalizedProviderPayload(
            city=centroid.city,
            provider=self.provider_slug,
            source_type="model",
            measured_at=measured_at,
            is_stale=is_timestamp_stale(measured_at),
            is_development_fixture=False,
            measurements=measurements,
        )

    async def fetch_city_stations(self, city: str) -> list[NormalizedStationTelemetry]:
        current = await self.fetch_city_measurements(city)
        centroid = lookup_city_centroid(city)
        if centroid is None:
            return []
        return [
            NormalizedStationTelemetry(
                external_station_id=f"open-meteo-cams-{centroid.city.lower()}",
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

    async def fetch_city_forecast(
        self, city: str, hours: int = 24
    ) -> NormalizedForecastPayload:
        centroid = require_city_centroid(city)
        bounded_hours = max(6, min(72, hours))
        forecast_days = max(2, math.ceil(bounded_hours / 24) + 1)
        body = await fetch_json_with_resilience(
            self.BASE_URL,
            params={
                "latitude": centroid.latitude,
                "longitude": centroid.longitude,
                "hourly": self.POLLUTANT_PARAMS,
                "forecast_days": forecast_days,
                "timeformat": "unixtime",
            },
            transport=self._transport,
        )
        hourly, times = self._require_hourly_payload(body)
        now = datetime.now(tz=UTC)
        cutoff = now + timedelta(hours=bounded_hours)
        future_indices = [
            idx
            for idx, ts in enumerate(times)
            if isinstance(ts, (int, float))
            and now <= datetime.fromtimestamp(int(ts), tz=UTC) <= cutoff
        ]
        slices: list[NormalizedForecastSlice] = []
        for pos, idx in enumerate(future_indices):
            if pos % 3 != 0:
                continue
            measurements = self._extract_hourly_index(hourly, idx)
            if not measurements:
                continue
            f_dt = datetime.fromtimestamp(int(times[idx]), tz=UTC)
            delta_h = (f_dt - now).total_seconds() / 3600.0
            slices.append(
                NormalizedForecastSlice(
                    forecast_for=f_dt,
                    measurements=measurements,
                    confidence_level=forecast_confidence_for_delta_hours(delta_h),
                )
            )
        if not slices:
            raise ExternalProviderUnavailableError()
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
        period_days_stride = {"24h": (1, 1), "7d": (7, 6), "30d": (30, 24)}
        days, stride = period_days_stride[period]
        body = await fetch_json_with_resilience(
            self.BASE_URL,
            params={
                "latitude": centroid.latitude,
                "longitude": centroid.longitude,
                "hourly": self.POLLUTANT_PARAMS,
                "past_days": days,
                "forecast_days": 1,
                "timeformat": "unixtime",
            },
            transport=self._transport,
        )
        hourly, times = self._require_hourly_payload(body)
        now = datetime.now(tz=UTC)
        start = now - timedelta(days=days)
        past_indices = [
            idx
            for idx, ts in enumerate(times)
            if isinstance(ts, (int, float))
            and start <= datetime.fromtimestamp(int(ts), tz=UTC) <= now
        ]
        points: list[NormalizedHistoryPoint] = []
        for pos, idx in enumerate(past_indices):
            if pos % stride != 0:
                continue
            measurements = self._extract_hourly_index(hourly, idx)
            if measurements:
                points.append(
                    NormalizedHistoryPoint(
                        timestamp=datetime.fromtimestamp(int(times[idx]), tz=UTC),
                        measurements=measurements,
                    )
                )
        return NormalizedHistoryPayload(
            city=centroid.city,
            provider=self.provider_slug,
            source_type="model",
            is_stale=False,
            is_development_fixture=False,
            points=points,
        )
