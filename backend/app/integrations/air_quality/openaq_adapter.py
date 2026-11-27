from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from app.core.exceptions import ExternalProviderUnavailableError
from app.integrations.air_quality.models import (
    CityCentroid,
    NormalizedForecastPayload,
    NormalizedHistoryPayload,
    NormalizedProviderPayload,
    NormalizedStationTelemetry,
    is_timestamp_stale,
    require_city_centroid,
)
from app.integrations.http_resilience import fetch_json_with_resilience
from app.services.air_quality.aqi_calculator import PollutantCode

_EPOCH_UTC = datetime.fromtimestamp(0, tz=UTC)
_POLLUTANT_NAME_MAP: dict[str, PollutantCode] = {
    "pm25": PollutantCode.PM25,
    "pm10": PollutantCode.PM10,
    "no2": PollutantCode.NO2,
    "so2": PollutantCode.SO2,
    "co": PollutantCode.CO,
    "o3": PollutantCode.O3,
}

@dataclass(frozen=True)
class _PendingOpenAQLocation:
    last_seen: datetime
    location_id: int
    station_name: str
    latitude: float
    longitude: float
    sensor_map: dict[int, tuple[str, str]]

class OpenAQAirQualityAdapter:
    """Live OpenAQ v3 REST adapter normalizing physical ground-station readings."""

    provider_slug = "openaq"
    BASE_URL = "https://api.openaq.org/v3"

    def __init__(
        self,
        api_key: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._transport = transport

    def _headers(self) -> dict[str, str]:
        if not self._api_key:
            raise ExternalProviderUnavailableError(
                code="AIR_QUALITY_CREDENTIALS_MISSING",
                message="OpenAQ API key is not configured.",
            )
        return {"X-API-Key": self._api_key, "Accept": "application/json"}

    @staticmethod
    def _parse_openaq_parameter(
        param_name: str, value: float, raw_unit: str
    ) -> tuple[PollutantCode, float, str] | None:
        code = _POLLUTANT_NAME_MAP.get(param_name.strip().lower())
        if code is None or value < 0:
            return None
        unit_clean = (
            raw_unit.strip()
            .lower()
            .replace("µg/m³", "ug/m3")
            .replace("μg/m³", "ug/m3")
        )
        if code == PollutantCode.CO and unit_clean == "ug/m3":
            return (code, round(value / 1000.0, 4), "mg/m3")
        if unit_clean in {"ug/m3", "mg/m3", "ppb", "ppm"}:
            return (code, float(value), unit_clean)
        return None

    @staticmethod
    def _parse_iso_utc(raw_dt: object) -> datetime | None:
        if not isinstance(raw_dt, str) or not raw_dt:
            return None
        try:
            return datetime.fromisoformat(raw_dt.replace("Z", "+00:00"))
        except ValueError:
            return None

    async def _fetch_location_latest(self, location_id: int) -> dict[str, Any]:
        return await fetch_json_with_resilience(
            f"{self.BASE_URL}/locations/{location_id}/latest",
            headers=self._headers(),
            transport=self._transport,
        )

    def _build_station(
        self,
        *,
        centroid: CityCentroid,
        station_id: str,
        name: str,
        latitude: float,
        longitude: float,
        measured_at: datetime,
        measurements: dict[PollutantCode, tuple[float, str]],
    ) -> NormalizedStationTelemetry:
        return NormalizedStationTelemetry(
            external_station_id=station_id,
            name=name,
            city=centroid.city,
            state_region=centroid.state_region,
            country_code=centroid.country_code,
            latitude=latitude,
            longitude=longitude,
            provider=self.provider_slug,
            source_type="station",
            measured_at=measured_at,
            is_stale=is_timestamp_stale(measured_at),
            is_development_fixture=False,
            measurements=measurements,
        )

    @classmethod
    def _extract_inline_sensors(
        cls, raw_sensors: object
    ) -> tuple[
        dict[PollutantCode, tuple[float, str]],
        datetime | None,
        dict[int, tuple[str, str]],
    ]:
        measurements: dict[PollutantCode, tuple[float, str]] = {}
        latest_dt: datetime | None = None
        sensor_map: dict[int, tuple[str, str]] = {}
        if not isinstance(raw_sensors, list):
            return measurements, latest_dt, sensor_map

        for sensor in raw_sensors:
            if not isinstance(sensor, dict):
                continue
            param_obj = sensor.get("parameter") or {}
            param_name = str(param_obj.get("name", ""))
            param_units = str(param_obj.get("units", ""))
            sensor_id = sensor.get("id")
            if isinstance(sensor_id, int) and not isinstance(sensor_id, bool):
                sensor_map[sensor_id] = (param_name, param_units)

            latest_obj = sensor.get("latest") or {}
            val = latest_obj.get("value")
            if not isinstance(val, (int, float)):
                continue
            parsed = cls._parse_openaq_parameter(param_name, float(val), param_units)
            if parsed is not None:
                measurements[parsed[0]] = (parsed[1], parsed[2])
            cand_dt = cls._parse_iso_utc((latest_obj.get("datetime") or {}).get("utc"))
            if cand_dt is not None and (latest_dt is None or cand_dt > latest_dt):
                latest_dt = cand_dt

        return measurements, latest_dt, sensor_map

    def _inspect_location_entry(
        self, entry: object, centroid: CityCentroid
    ) -> tuple[NormalizedStationTelemetry | None, _PendingOpenAQLocation | None]:
        if not isinstance(entry, dict):
            return None, None
        coords = entry.get("coordinates") or {}
        lat = coords.get("latitude")
        lon = coords.get("longitude")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            return None, None

        station_name = str(entry.get("name", f"{centroid.city} Station"))
        measurements, latest_dt, sensor_map = self._extract_inline_sensors(entry.get("sensors"))
        if measurements:
            station = self._build_station(
                centroid=centroid,
                station_id=str(entry.get("id", "openaq-station")),
                name=station_name,
                latitude=float(lat),
                longitude=float(lon),
                measured_at=latest_dt or datetime.now(tz=UTC),
                measurements=measurements,
            )
            return station, None

        loc_id = entry.get("id")
        if sensor_map and isinstance(loc_id, int) and not isinstance(loc_id, bool):
            last_seen = (
                self._parse_iso_utc((entry.get("datetimeLast") or {}).get("utc")) or _EPOCH_UTC
            )
            return None, _PendingOpenAQLocation(
                last_seen=last_seen,
                location_id=loc_id,
                station_name=station_name,
                latitude=float(lat),
                longitude=float(lon),
                sensor_map=sensor_map,
            )
        return None, None

    @classmethod
    def _parse_latest_rows(
        cls, rows: object, sensor_map: dict[int, tuple[str, str]]
    ) -> tuple[dict[PollutantCode, tuple[float, str]], datetime | None]:
        measurements: dict[PollutantCode, tuple[float, str]] = {}
        latest_dt: datetime | None = None
        if not isinstance(rows, list):
            return measurements, latest_dt

        for row in rows:
            if not isinstance(row, dict):
                continue
            s_id = row.get("sensorsId")
            val = row.get("value")
            if (
                not isinstance(s_id, int)
                or isinstance(s_id, bool)
                or s_id not in sensor_map
                or not isinstance(val, (int, float))
            ):
                continue
            p_name, p_units = sensor_map[s_id]
            parsed = cls._parse_openaq_parameter(p_name, float(val), p_units)
            if parsed is not None:
                measurements[parsed[0]] = (parsed[1], parsed[2])
            cand_dt = cls._parse_iso_utc((row.get("datetime") or {}).get("utc"))
            if cand_dt is not None and (latest_dt is None or cand_dt > latest_dt):
                latest_dt = cand_dt

        return measurements, latest_dt

    async def _hydrate_pending_locations(
        self, pending: list[_PendingOpenAQLocation], centroid: CityCentroid
    ) -> list[NormalizedStationTelemetry]:
        ordered = sorted(
            pending,
            key=lambda item: (item.last_seen, len(item.sensor_map)),
            reverse=True,
        )[:4]
        batches = await asyncio.gather(
            *(self._fetch_location_latest(item.location_id) for item in ordered),
            return_exceptions=True,
        )
        hydrated: list[NormalizedStationTelemetry] = []
        for item, res in zip(ordered, batches, strict=True):
            if not isinstance(res, dict):
                continue
            loc_measurements, loc_dt = self._parse_latest_rows(res.get("results"), item.sensor_map)
            if loc_measurements:
                hydrated.append(
                    self._build_station(
                        centroid=centroid,
                        station_id=str(item.location_id),
                        name=item.station_name,
                        latitude=item.latitude,
                        longitude=item.longitude,
                        measured_at=loc_dt or datetime.now(tz=UTC),
                        measurements=loc_measurements,
                    )
                )
        return hydrated

    async def fetch_city_stations(self, city: str) -> list[NormalizedStationTelemetry]:
        centroid = require_city_centroid(city)
        payload = await fetch_json_with_resilience(
            f"{self.BASE_URL}/locations",
            params={
                "coordinates": f"{centroid.latitude},{centroid.longitude}",
                "radius": 25000,
                "limit": 10,
            },
            headers=self._headers(),
            transport=self._transport,
        )
        raw_results = payload.get("results")
        if not isinstance(raw_results, list) or not raw_results:
            raise ExternalProviderUnavailableError(
                code="AIR_QUALITY_NO_UPSTREAM_STATIONS",
                message=f"No active OpenAQ monitoring stations responded near {centroid.city}.",
            )

        stations: list[NormalizedStationTelemetry] = []
        pending_locations: list[_PendingOpenAQLocation] = []
        for entry in raw_results:
            station, pending = self._inspect_location_entry(entry, centroid)
            if station is not None:
                stations.append(station)
            elif pending is not None:
                pending_locations.append(pending)

        if not stations and pending_locations:
            stations = await self._hydrate_pending_locations(pending_locations, centroid)

        if not stations:
            raise ExternalProviderUnavailableError(
                code="AIR_QUALITY_NO_VALID_MEASUREMENTS",
                message=f"OpenAQ stations near {centroid.city} reported no valid pollutants.",
            )
        return stations

    async def fetch_city_measurements(self, city: str) -> NormalizedProviderPayload:
        stations = await self.fetch_city_stations(city)
        aggregated: dict[PollutantCode, list[tuple[float, str]]] = {}
        newest_ts = max(st.measured_at for st in stations)
        for st in stations:
            for code, (val, unit) in st.measurements.items():
                aggregated.setdefault(code, []).append((val, unit))

        averaged: dict[PollutantCode, tuple[float, str]] = {}
        for code, samples in aggregated.items():
            unit = samples[0][1]
            same_unit_vals = [v for v, u in samples if u == unit]
            averaged[code] = (round(sum(same_unit_vals) / len(same_unit_vals), 2), unit)

        return NormalizedProviderPayload(
            city=stations[0].city,
            provider=self.provider_slug,
            source_type="station",
            measured_at=newest_ts,
            is_stale=is_timestamp_stale(newest_ts),
            is_development_fixture=False,
            measurements=averaged,
        )

    async def fetch_city_forecast(
        self, city: str, hours: int = 24
    ) -> NormalizedForecastPayload:
        raise ExternalProviderUnavailableError(
            code="AIR_QUALITY_FORECAST_DELEGATED",
            message=(
                f"OpenAQ tracks ground observations; {hours}h forecast for {city} "
                "delegates to model fallback."
            ),
        )

    async def fetch_city_history(
        self, city: str, period: Literal["24h", "7d", "30d"]
    ) -> NormalizedHistoryPayload:
        raise ExternalProviderUnavailableError(
            code="AIR_QUALITY_HISTORY_DELEGATED",
            message=(
                f"Historical rollup for {city} ({period}) uses persisted DB series "
                "or fallback provider."
            ),
        )
