"""Explicitly labeled deterministic development/CI air quality fixture adapter."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import ClassVar, Literal

from app.core.exceptions import ExternalProviderUnavailableError
from app.integrations.air_quality.models import (
    CityCentroid,
    NormalizedForecastPayload,
    NormalizedForecastSlice,
    NormalizedHistoryPayload,
    NormalizedHistoryPoint,
    NormalizedProviderPayload,
    NormalizedStationTelemetry,
    forecast_confidence_for_delta_hours,
    lookup_city_centroid,
)
from app.services.air_quality.aqi_calculator import PollutantCode


class DevelopmentFixtureAirQualityAdapter:
    """Explicitly labeled development fixture adapter.

    Prohibited in production by Settings.validate_production_invariants().
    Every reading sets is_development_fixture=True so UI never mistakes it for live telemetry.
    """

    provider_slug = "development_fixture"

    FIXTURE_CITIES: ClassVar[dict[str, dict[PollutantCode, tuple[float, str]]]] = {
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
        return [
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
                measurements={
                    code: (round(val * factor, 2), unit) for code, (val, unit) in sample.items()
                },
            )
            for suffix, label, d_lat, d_lon, factor in offsets
        ]

    async def fetch_city_forecast(self, city: str, hours: int = 24) -> NormalizedForecastPayload:
        centroid, sample = self._resolve_city_base(city)
        now = datetime.now(tz=UTC).replace(minute=0, second=0, microsecond=0)
        bounded_hours = max(6, min(72, hours))
        slices: list[NormalizedForecastSlice] = []

        for step in range(1, bounded_hours + 1, 3):
            target_dt = now + timedelta(hours=step)
            ist_hour = (target_dt.hour + 5) % 24
            diurnal_multiplier = 0.78 if 12 <= ist_hour <= 16 else (1.16 if ist_hour <= 8 else 1.0)
            slices.append(
                NormalizedForecastSlice(
                    forecast_for=target_dt,
                    measurements={
                        code: (round(val * diurnal_multiplier, 2), unit)
                        for code, (val, unit) in sample.items()
                    },
                    confidence_level=forecast_confidence_for_delta_hours(step),
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
        count_stride_map: dict[str, tuple[int, int]] = {
            "24h": (24, 1),
            "7d": (28, 6),
            "30d": (30, 24),
        }
        count, step_hours = count_stride_map[period]
        points = [
            NormalizedHistoryPoint(
                timestamp=now - timedelta(hours=idx * step_hours),
                measurements={
                    code: (round(max(1.0, val * (1.0 + 0.18 * math.sin(idx * 0.65))), 2), unit)
                    for code, (val, unit) in sample.items()
                },
            )
            for idx in range(count, 0, -1)
        ]

        return NormalizedHistoryPayload(
            city=centroid.city,
            provider=self.provider_slug,
            source_type="station",
            is_stale=False,
            is_development_fixture=True,
            points=points,
        )
