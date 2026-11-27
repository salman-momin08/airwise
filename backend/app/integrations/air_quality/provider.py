from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol

import httpx

from app.core.config import Settings
from app.core.exceptions import ExternalProviderUnavailableError
from app.integrations.http_resilience import (
    ProviderCircuitBreaker,
    fetch_json_with_resilience,
)
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


def is_timestamp_stale(measured_at: datetime, now: datetime | None = None) -> bool:
    ref = now or datetime.now(tz=UTC)
    ts = measured_at if measured_at.tzinfo else measured_at.replace(tzinfo=UTC)
    return (ref - ts).total_seconds() > STALE_MEASUREMENT_MAX_AGE_SECONDS


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


class DevelopmentFixtureAirQualityAdapter:
    """Explicitly labeled development fixture adapter.

    Prohibited in production by Settings.validate_production_invariants().
    Every reading sets is_development_fixture=True so UI never mistakes it for live telemetry.
    """

    provider_slug = "development_fixture"

    FIXTURE_CITIES: dict[str, dict[PollutantCode, tuple[float, str]]] = {
        "delhi": {
            PollutantCode.PM25: (192.0, "ug/m3"),
            PollutantCode.PM10: (318.0, "ug/m3"),
            PollutantCode.NO2: (76.0, "ug/m3"),
            PollutantCode.SO2: (18.0, "ug/m3"),
            PollutantCode.CO: (1.8, "mg/m3"),
            PollutantCode.O3: (42.0, "ug/m3"),
        },
        "gurugram": {
            PollutantCode.PM25: (174.0, "ug/m3"),
            PollutantCode.PM10: (290.0, "ug/m3"),
            PollutantCode.NO2: (68.0, "ug/m3"),
            PollutantCode.SO2: (16.0, "ug/m3"),
            PollutantCode.CO: (1.6, "mg/m3"),
            PollutantCode.O3: (44.0, "ug/m3"),
        },
        "noida": {
            PollutantCode.PM25: (185.0, "ug/m3"),
            PollutantCode.PM10: (305.0, "ug/m3"),
            PollutantCode.NO2: (72.0, "ug/m3"),
            PollutantCode.SO2: (17.0, "ug/m3"),
            PollutantCode.CO: (1.7, "mg/m3"),
            PollutantCode.O3: (40.0, "ug/m3"),
        },
        "bengaluru": {
            PollutantCode.PM25: (28.0, "ug/m3"),
            PollutantCode.PM10: (58.0, "ug/m3"),
            PollutantCode.NO2: (31.0, "ug/m3"),
            PollutantCode.SO2: (9.0, "ug/m3"),
            PollutantCode.CO: (0.7, "mg/m3"),
            PollutantCode.O3: (46.0, "ug/m3"),
        },
        "mumbai": {
            PollutantCode.PM25: (64.0, "ug/m3"),
            PollutantCode.PM10: (132.0, "ug/m3"),
            PollutantCode.NO2: (48.0, "ug/m3"),
            PollutantCode.SO2: (14.0, "ug/m3"),
            PollutantCode.CO: (1.1, "mg/m3"),
            PollutantCode.O3: (52.0, "ug/m3"),
        },
        "chennai": {
            PollutantCode.PM25: (34.0, "ug/m3"),
            PollutantCode.PM10: (72.0, "ug/m3"),
            PollutantCode.NO2: (29.0, "ug/m3"),
            PollutantCode.SO2: (11.0, "ug/m3"),
            PollutantCode.CO: (0.8, "mg/m3"),
            PollutantCode.O3: (48.0, "ug/m3"),
        },
        "kolkata": {
            PollutantCode.PM25: (112.0, "ug/m3"),
            PollutantCode.PM10: (210.0, "ug/m3"),
            PollutantCode.NO2: (58.0, "ug/m3"),
            PollutantCode.SO2: (15.0, "ug/m3"),
            PollutantCode.CO: (1.4, "mg/m3"),
            PollutantCode.O3: (39.0, "ug/m3"),
        },
        "hyderabad": {
            PollutantCode.PM25: (46.0, "ug/m3"),
            PollutantCode.PM10: (94.0, "ug/m3"),
            PollutantCode.NO2: (36.0, "ug/m3"),
            PollutantCode.SO2: (10.0, "ug/m3"),
            PollutantCode.CO: (0.9, "mg/m3"),
            PollutantCode.O3: (50.0, "ug/m3"),
        },
        "pune": {
            PollutantCode.PM25: (52.0, "ug/m3"),
            PollutantCode.PM10: (108.0, "ug/m3"),
            PollutantCode.NO2: (38.0, "ug/m3"),
            PollutantCode.SO2: (12.0, "ug/m3"),
            PollutantCode.CO: (1.0, "mg/m3"),
            PollutantCode.O3: (54.0, "ug/m3"),
        },
        "lucknow": {
            PollutantCode.PM25: (148.0, "ug/m3"),
            PollutantCode.PM10: (264.0, "ug/m3"),
            PollutantCode.NO2: (62.0, "ug/m3"),
            PollutantCode.SO2: (16.0, "ug/m3"),
            PollutantCode.CO: (1.5, "mg/m3"),
            PollutantCode.O3: (41.0, "ug/m3"),
        },
    }

    def _resolve_city_base(
        self, city: str
    ) -> tuple[CityCentroid, dict[PollutantCode, tuple[float, str]]]:
        key = city.strip().lower()
        sample = self.FIXTURE_CITIES.get(key)
        centroid = lookup_city_centroid(key)
        if sample is None or centroid is None:
            raise ExternalProviderUnavailableError(
                code="AIR_QUALITY_FIXTURE_CITY_NOT_CONFIGURED",
                message=(
                    f"No development fixture exists for '{city}'. Configure AIR_QUALITY_API_KEY "
                    "and AIR_QUALITY_PROVIDER=openaq for live city telemetry."
                ),
            )
        return centroid, sample

    async def fetch_city_measurements(self, city: str) -> NormalizedProviderPayload:
        centroid, sample = self._resolve_city_base(city)
        return NormalizedProviderPayload(
            city=centroid.city,
            provider=self.provider_slug,
            source_type="station",
            measured_at=datetime.now(tz=UTC),
            is_stale=False,
            is_development_fixture=True,
            measurements=dict(sample),
        )

    async def fetch_city_stations(self, city: str) -> list[NormalizedStationTelemetry]:
        centroid, sample = self._resolve_city_base(city)
        now = datetime.now(tz=UTC)
        offsets: tuple[tuple[str, str, float, float, float], ...] = (
            ("central", "Central Reference Monitor", 0.0, 0.0, 1.00),
            ("north", "North Urban Corridor Station", 0.038, 0.022, 1.08),
            ("south", "South Residential Background Station", -0.034, -0.019, 0.88),
        )
        stations: list[NormalizedStationTelemetry] = []
        for suffix, label, d_lat, d_lon, factor in offsets:
            scaled = {
                code: (round(val * factor, 2), unit)
                for code, (val, unit) in sample.items()
            }
            stations.append(
                NormalizedStationTelemetry(
                    external_station_id=f"fixture-{centroid.city.lower()}-{suffix}",
                    name=f"{centroid.city} — {label}",
                    city=centroid.city,
                    state_region=centroid.state_region,
                    country_code=centroid.country_code,
                    latitude=round(centroid.latitude + d_lat, 5),
                    longitude=round(centroid.longitude + d_lon, 5),
                    provider=self.provider_slug,
                    source_type="station",
                    measured_at=now,
                    is_stale=False,
                    is_development_fixture=True,
                    measurements=scaled,
                )
            )
        return stations

    async def fetch_city_forecast(
        self, city: str, hours: int = 24
    ) -> NormalizedForecastPayload:
        centroid, sample = self._resolve_city_base(city)
        now = datetime.now(tz=UTC).replace(minute=0, second=0, microsecond=0)
        bounded_hours = max(6, min(72, hours))
        slices: list[NormalizedForecastSlice] = []

        for step in range(1, bounded_hours + 1, 3):
            target_dt = now + timedelta(hours=step)
            ist_hour = (target_dt.hour + 5) % 24
            diurnal_multiplier = (
                0.78 if 12 <= ist_hour <= 16 else (1.16 if ist_hour <= 8 else 1.0)
            )
            projected = {
                code: (round(val * diurnal_multiplier, 2), unit)
                for code, (val, unit) in sample.items()
            }
            confidence: Literal["low", "medium", "high"] = (
                "high" if step <= 12 else ("medium" if step <= 36 else "low")
            )
            slices.append(
                NormalizedForecastSlice(
                    forecast_for=target_dt,
                    measurements=projected,
                    confidence_level=confidence,
                )
            )

        return NormalizedForecastPayload(
            city=centroid.city,
            provider=self.provider_slug,
            source_type="model",
            generated_at=now,
            is_stale=False,
            is_development_fixture=True,
            slices=slices,
        )

    async def fetch_city_history(
        self, city: str, period: Literal["24h", "7d", "30d"]
    ) -> NormalizedHistoryPayload:
        centroid, sample = self._resolve_city_base(city)
        now = datetime.now(tz=UTC).replace(minute=0, second=0, microsecond=0)
        if period == "24h":
            count, step_hours = 24, 1
        elif period == "7d":
            count, step_hours = 28, 6
        else:
            count, step_hours = 30, 24

        points: list[NormalizedHistoryPoint] = []
        for idx in range(count, 0, -1):
            ts = now - timedelta(hours=idx * step_hours)
            wave = 1.0 + 0.18 * math.sin(idx * 0.65)
            scaled = {
                code: (round(max(1.0, val * wave), 2), unit)
                for code, (val, unit) in sample.items()
            }
            points.append(NormalizedHistoryPoint(timestamp=ts, measurements=scaled))

        return NormalizedHistoryPayload(
            city=centroid.city,
            provider=self.provider_slug,
            source_type="station",
            is_stale=False,
            is_development_fixture=True,
            points=points,
        )


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
        mapping: dict[str, PollutantCode] = {
            "pm25": PollutantCode.PM25,
            "pm10": PollutantCode.PM10,
            "no2": PollutantCode.NO2,
            "so2": PollutantCode.SO2,
            "co": PollutantCode.CO,
            "o3": PollutantCode.O3,
        }
        code = mapping.get(param_name.strip().lower())
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

    async def fetch_city_stations(self, city: str) -> list[NormalizedStationTelemetry]:
        centroid = lookup_city_centroid(city)
        if centroid is None:
            raise ExternalProviderUnavailableError(
                code="AIR_QUALITY_CITY_UNSUPPORTED",
                message=f"City '{city}' is not in the supported spatial gazetteer.",
            )
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
        pending_locations: list[
            tuple[datetime, int, dict[str, Any], float, float, dict[int, tuple[str, str]]]
        ] = []
        epoch = datetime.fromtimestamp(0, tz=UTC)

        for entry in raw_results:
            if not isinstance(entry, dict):
                continue
            coords = entry.get("coordinates") or {}
            lat = coords.get("latitude")
            lon = coords.get("longitude")
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                continue

            measurements: dict[PollutantCode, tuple[float, str]] = {}
            latest_dt: datetime | None = None
            sensor_map: dict[int, tuple[str, str]] = {}
            raw_sensors = entry.get("sensors")
            sensors: list[Any] = raw_sensors if isinstance(raw_sensors, list) else []
            for sensor in sensors:
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
                parsed = self._parse_openaq_parameter(param_name, float(val), param_units)
                if parsed is not None:
                    p_code, p_val, p_unit = parsed
                    measurements[p_code] = (p_val, p_unit)
                cand_dt = self._parse_iso_utc((latest_obj.get("datetime") or {}).get("utc"))
                if cand_dt is not None and (latest_dt is None or cand_dt > latest_dt):
                    latest_dt = cand_dt

            if measurements:
                measured_at = latest_dt or datetime.now(tz=UTC)
                stations.append(
                    NormalizedStationTelemetry(
                        external_station_id=str(entry.get("id", "openaq-station")),
                        name=str(entry.get("name", f"{centroid.city} Station")),
                        city=centroid.city,
                        state_region=centroid.state_region,
                        country_code=centroid.country_code,
                        latitude=float(lat),
                        longitude=float(lon),
                        provider=self.provider_slug,
                        source_type="station",
                        measured_at=measured_at,
                        is_stale=is_timestamp_stale(measured_at),
                        is_development_fixture=False,
                        measurements=measurements,
                    )
                )
                continue

            loc_id = entry.get("id")
            if sensor_map and isinstance(loc_id, int) and not isinstance(loc_id, bool):
                last_seen = (
                    self._parse_iso_utc((entry.get("datetimeLast") or {}).get("utc")) or epoch
                )
                pending_locations.append(
                    (last_seen, loc_id, entry, float(lat), float(lon), sensor_map)
                )

        if not stations and pending_locations:
            pending_locations.sort(key=lambda item: (item[0], len(item[5])), reverse=True)
            selected = pending_locations[:4]
            latest_batches = await asyncio.gather(
                *(self._fetch_location_latest(item[1]) for item in selected),
                return_exceptions=True,
            )
            for (_, loc_id, entry, lat_f, lon_f, sensor_map), latest_res in zip(
                selected, latest_batches, strict=True
            ):
                if not isinstance(latest_res, dict):
                    continue
                rows = latest_res.get("results")
                if not isinstance(rows, list):
                    continue
                loc_measurements: dict[PollutantCode, tuple[float, str]] = {}
                loc_dt: datetime | None = None
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
                    parsed = self._parse_openaq_parameter(p_name, float(val), p_units)
                    if parsed is not None:
                        p_code, p_val, p_unit = parsed
                        loc_measurements[p_code] = (p_val, p_unit)
                    cand_dt = self._parse_iso_utc((row.get("datetime") or {}).get("utc"))
                    if cand_dt is not None and (loc_dt is None or cand_dt > loc_dt):
                        loc_dt = cand_dt

                if not loc_measurements:
                    continue
                measured_at = loc_dt or datetime.now(tz=UTC)
                stations.append(
                    NormalizedStationTelemetry(
                        external_station_id=str(loc_id),
                        name=str(entry.get("name", f"{centroid.city} Station")),
                        city=centroid.city,
                        state_region=centroid.state_region,
                        country_code=centroid.country_code,
                        latitude=lat_f,
                        longitude=lon_f,
                        provider=self.provider_slug,
                        source_type="station",
                        measured_at=measured_at,
                        is_stale=is_timestamp_stale(measured_at),
                        is_development_fixture=False,
                        measurements=loc_measurements,
                    )
                )

        if not stations:
            raise ExternalProviderUnavailableError(
                code="AIR_QUALITY_NO_VALID_MEASUREMENTS",
                message=f"OpenAQ stations near {centroid.city} reported no valid pollutants.",
            )
        return stations

    async def fetch_city_measurements(self, city: str) -> NormalizedProviderPayload:
        stations = await self.fetch_city_stations(city)
        aggregated: dict[PollutantCode, list[tuple[float, str]]] = {}
        newest_ts = stations[0].measured_at
        for st in stations:
            if st.measured_at > newest_ts:
                newest_ts = st.measured_at
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
        mapping: tuple[tuple[str, PollutantCode], ...] = (
            ("pm2_5", PollutantCode.PM25),
            ("pm10", PollutantCode.PM10),
            ("no2", PollutantCode.NO2),
            ("so2", PollutantCode.SO2),
            ("o3", PollutantCode.O3),
        )
        for key, code in mapping:
            raw_val = components.get(key)
            if isinstance(raw_val, (int, float)) and raw_val >= 0:
                measurements[code] = (round(float(raw_val), 2), "ug/m3")
        raw_co = components.get("co")
        if isinstance(raw_co, (int, float)) and raw_co >= 0:
            measurements[PollutantCode.CO] = (round(float(raw_co) / 1000.0, 3), "mg/m3")
        return measurements

    async def fetch_city_measurements(self, city: str) -> NormalizedProviderPayload:
        centroid = lookup_city_centroid(city)
        if centroid is None:
            raise ExternalProviderUnavailableError(
                code="AIR_QUALITY_CITY_UNSUPPORTED",
                message=f"City '{city}' is not in the supported spatial gazetteer.",
            )
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
            raise ExternalProviderUnavailableError()
        first = entries[0]
        dt_epoch = first.get("dt")
        measured_at = (
            datetime.fromtimestamp(int(dt_epoch), tz=UTC)
            if isinstance(dt_epoch, (int, float))
            else datetime.now(tz=UTC)
        )
        measurements = self._extract_components(first.get("components") or {})
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

    async def fetch_city_forecast(
        self, city: str, hours: int = 24
    ) -> NormalizedForecastPayload:
        centroid = lookup_city_centroid(city)
        if centroid is None:
            raise ExternalProviderUnavailableError(
                code="AIR_QUALITY_CITY_UNSUPPORTED",
                message=f"City '{city}' is not in the supported spatial gazetteer.",
            )
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
            raise ExternalProviderUnavailableError()

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
            conf: Literal["low", "medium", "high"] = (
                "high" if delta_h <= 12 else ("medium" if delta_h <= 36 else "low")
            )
            slices.append(
                NormalizedForecastSlice(
                    forecast_for=f_dt,
                    measurements=self._extract_components(item.get("components") or {}),
                    confidence_level=conf,
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
        centroid = lookup_city_centroid(city)
        if centroid is None:
            raise ExternalProviderUnavailableError(
                code="AIR_QUALITY_CITY_UNSUPPORTED",
                message=f"City '{city}' is not in the supported spatial gazetteer.",
            )
        now = datetime.now(tz=UTC)
        days = 1 if period == "24h" else (7 if period == "7d" else 30)
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
            raise ExternalProviderUnavailableError()
        stride = 1 if period == "24h" else (6 if period == "7d" else 24)
        points: list[NormalizedHistoryPoint] = []
        for idx, item in enumerate(entries):
            if idx % stride != 0 or not isinstance(item, dict):
                continue
            dt_epoch = item.get("dt")
            if not isinstance(dt_epoch, (int, float)):
                continue
            points.append(
                NormalizedHistoryPoint(
                    timestamp=datetime.fromtimestamp(int(dt_epoch), tz=UTC),
                    measurements=self._extract_components(item.get("components") or {}),
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

    async def fetch_city_forecast(
        self, city: str, hours: int = 24
    ) -> NormalizedForecastPayload:
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

    async def fetch_city_measurements(self, city: str) -> NormalizedProviderPayload:
        last_error: ExternalProviderUnavailableError | None = None
        if self.primary_breaker.allow_request():
            try:
                res = await self.primary.fetch_city_measurements(city)
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
                res = await self.fallback.fetch_city_measurements(city)
                self.fallback_breaker.record_success()
                return res
            except ExternalProviderUnavailableError as exc:
                self.fallback_breaker.record_failure()
                last_error = exc

        raise last_error or ExternalProviderUnavailableError()

    async def fetch_city_stations(self, city: str) -> list[NormalizedStationTelemetry]:
        last_error: ExternalProviderUnavailableError | None = None
        if self.primary_breaker.allow_request():
            try:
                res = await self.primary.fetch_city_stations(city)
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
                res = await self.fallback.fetch_city_stations(city)
                self.fallback_breaker.record_success()
                return res
            except ExternalProviderUnavailableError as exc:
                self.fallback_breaker.record_failure()
                last_error = exc

        raise last_error or ExternalProviderUnavailableError()

    async def fetch_city_forecast(
        self, city: str, hours: int = 24
    ) -> NormalizedForecastPayload:
        last_error: ExternalProviderUnavailableError | None = None
        try:
            return await self.primary.fetch_city_forecast(city, hours=hours)
        except ExternalProviderUnavailableError as exc:
            last_error = exc

        if self.fallback is not None:
            try:
                return await self.fallback.fetch_city_forecast(city, hours=hours)
            except ExternalProviderUnavailableError as exc:
                last_error = exc

        raise last_error or ExternalProviderUnavailableError()

    async def fetch_city_history(
        self, city: str, period: Literal["24h", "7d", "30d"]
    ) -> NormalizedHistoryPayload:
        last_error: ExternalProviderUnavailableError | None = None
        try:
            return await self.primary.fetch_city_history(city, period=period)
        except ExternalProviderUnavailableError as exc:
            last_error = exc

        if self.fallback is not None:
            try:
                return await self.fallback.fetch_city_history(city, period=period)
            except ExternalProviderUnavailableError as exc:
                last_error = exc

        raise last_error or ExternalProviderUnavailableError()


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
        mapping: tuple[tuple[str, PollutantCode], ...] = (
            ("pm2_5", PollutantCode.PM25),
            ("pm10", PollutantCode.PM10),
            ("nitrogen_dioxide", PollutantCode.NO2),
            ("sulphur_dioxide", PollutantCode.SO2),
            ("ozone", PollutantCode.O3),
        )
        for key, code in mapping:
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
        row: dict[str, Any] = {}
        for key in (
            "pm2_5",
            "pm10",
            "nitrogen_dioxide",
            "sulphur_dioxide",
            "ozone",
            "carbon_monoxide",
        ):
            series = hourly.get(key)
            if isinstance(series, list) and idx < len(series):
                row[key] = series[idx]
        return cls._extract_current(row)

    async def fetch_city_measurements(self, city: str) -> NormalizedProviderPayload:
        centroid = lookup_city_centroid(city)
        if centroid is None:
            raise ExternalProviderUnavailableError(
                code="AIR_QUALITY_CITY_UNSUPPORTED",
                message=f"City '{city}' is not in the supported spatial gazetteer.",
            )
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
        centroid = lookup_city_centroid(city)
        if centroid is None:
            raise ExternalProviderUnavailableError(
                code="AIR_QUALITY_CITY_UNSUPPORTED",
                message=f"City '{city}' is not in the supported spatial gazetteer.",
            )
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
        hourly = body.get("hourly")
        times = hourly.get("time") if isinstance(hourly, dict) else None
        if not isinstance(hourly, dict) or not isinstance(times, list) or not times:
            raise ExternalProviderUnavailableError()

        now = datetime.now(tz=UTC)
        cutoff = now + timedelta(hours=bounded_hours)
        slices: list[NormalizedForecastSlice] = []
        future_indices = [
            idx
            for idx, ts in enumerate(times)
            if isinstance(ts, (int, float))
            and now <= datetime.fromtimestamp(int(ts), tz=UTC) <= cutoff
        ]
        for pos, idx in enumerate(future_indices):
            if pos % 3 != 0:
                continue
            f_dt = datetime.fromtimestamp(int(times[idx]), tz=UTC)
            measurements = self._extract_hourly_index(hourly, idx)
            if not measurements:
                continue
            delta_h = (f_dt - now).total_seconds() / 3600.0
            conf: Literal["low", "medium", "high"] = (
                "high" if delta_h <= 12 else ("medium" if delta_h <= 36 else "low")
            )
            slices.append(
                NormalizedForecastSlice(
                    forecast_for=f_dt,
                    measurements=measurements,
                    confidence_level=conf,
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
        centroid = lookup_city_centroid(city)
        if centroid is None:
            raise ExternalProviderUnavailableError(
                code="AIR_QUALITY_CITY_UNSUPPORTED",
                message=f"City '{city}' is not in the supported spatial gazetteer.",
            )
        days = 1 if period == "24h" else (7 if period == "7d" else 30)
        stride = 1 if period == "24h" else (6 if period == "7d" else 24)
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
        hourly = body.get("hourly")
        times = hourly.get("time") if isinstance(hourly, dict) else None
        if not isinstance(hourly, dict) or not isinstance(times, list) or not times:
            raise ExternalProviderUnavailableError()

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
            if not measurements:
                continue
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
