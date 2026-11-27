"""Spatial and time-series repository for air quality stations, measurements, and sources."""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.air_quality.provider import NormalizedStationTelemetry
from app.integrations.weather.provider import NormalizedWeatherPayload
from app.models.telemetry import (
    AirQualityMeasurement,
    AirQualitySource,
    AirQualityStation,
    WeatherObservation,
)
from app.services.air_quality.aqi_calculator import PollutantCode

EARTH_RADIUS_KM = 6371.0


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two WGS84 coordinates."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    return round(2.0 * EARTH_RADIUS_KM * math.atan2(math.sqrt(a), math.sqrt(1.0 - a)), 2)


class TelemetryRepository:
    """Async SQLAlchemy 2.x repository for environmental sources, stations, and time series."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _is_postgresql(self) -> bool:
        return self._session.get_bind().dialect.name == "postgresql"

    def _point_value(self, latitude: float, longitude: float) -> Any:
        wkt = f"POINT({longitude} {latitude})"
        if self._is_postgresql():
            return WKTElement(wkt, srid=4326)
        return wkt

    async def ensure_source(
        self,
        *,
        slug: str,
        name: str,
        provider_type: str,
        priority_rank: int = 1,
    ) -> AirQualitySource:
        stmt = select(AirQualitySource).where(AirQualitySource.slug == slug)
        existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            return existing

        source = AirQualitySource(
            id=uuid.uuid4(),
            slug=slug,
            name=name,
            provider_type=provider_type,
            refresh_interval_seconds=900,
            is_enabled=True,
            priority_rank=priority_rank,
        )
        self._session.add(source)
        await self._session.flush()
        return source

    async def upsert_station_with_measurements(
        self, station_data: NormalizedStationTelemetry
    ) -> AirQualityStation:
        source = await self.ensure_source(
            slug=station_data.provider,
            name=f"AirWise {station_data.provider.replace('_', ' ').title()} Feed",
            provider_type=station_data.source_type,
        )
        stmt = select(AirQualityStation).where(
            AirQualityStation.source_id == source.id,
            AirQualityStation.external_station_id == station_data.external_station_id,
        )
        station = (await self._session.execute(stmt)).scalar_one_or_none()
        if station is None:
            station = AirQualityStation(
                id=uuid.uuid4(),
                source_id=source.id,
                external_station_id=station_data.external_station_id,
                name=station_data.name,
                city=station_data.city,
                state_region=station_data.state_region,
                country_code=station_data.country_code,
                coordinates=self._point_value(station_data.latitude, station_data.longitude),
                latitude=station_data.latitude,
                longitude=station_data.longitude,
                source_type=station_data.source_type,
                is_active=True,
            )
            self._session.add(station)
            await self._session.flush()
        else:
            station.name = station_data.name
            station.latitude = station_data.latitude
            station.longitude = station_data.longitude
            station.coordinates = self._point_value(station_data.latitude, station_data.longitude)

        measured_utc = (
            station_data.measured_at.astimezone(UTC)
            if station_data.measured_at.tzinfo
            else station_data.measured_at.replace(tzinfo=UTC)
        )

        existing_polls_stmt = select(AirQualityMeasurement.pollutant).where(
            AirQualityMeasurement.station_id == station.id,
            AirQualityMeasurement.measured_at == measured_utc,
        )
        existing_polls = set((await self._session.execute(existing_polls_stmt)).scalars().all())

        now = datetime.now(tz=UTC)
        for code, (conc, unit) in station_data.measurements.items():
            if code.value in existing_polls:
                continue
            self._session.add(
                AirQualityMeasurement(
                    id=uuid.uuid4(),
                    measured_at=measured_utc,
                    station_id=station.id,
                    source_id=source.id,
                    pollutant=code.value,
                    concentration=Decimal(str(round(conc, 4))),
                    unit=unit,
                    averaging_period_hours=8 if code.value in {"co", "o3"} else 24,
                    source_timezone="Asia/Kolkata",
                    ingested_at=now,
                    quality_flag=(
                        "development_fixture" if station_data.is_development_fixture else "verified"
                    ),
                )
            )
        return station

    async def record_weather_observation(
        self, payload: NormalizedWeatherPayload
    ) -> WeatherObservation:
        obs = WeatherObservation(
            id=uuid.uuid4(),
            city=payload.city,
            coordinates=self._point_value(payload.latitude, payload.longitude),
            latitude=payload.latitude,
            longitude=payload.longitude,
            temperature_c=payload.temperature_c,
            humidity_pct=payload.humidity_pct,
            wind_speed_mps=payload.wind_speed_mps,
            wind_direction_deg=payload.wind_direction_deg,
            inversion_risk_flag=payload.inversion_risk_flag,
            observed_at=payload.observed_at,
            provider=payload.provider,
            is_stale=payload.is_stale,
            is_development_fixture=payload.is_development_fixture,
        )
        self._session.add(obs)
        return obs

    async def list_stations_in_bbox(
        self,
        *,
        min_lon: float,
        min_lat: float,
        max_lon: float,
        max_lat: float,
    ) -> list[
        tuple[
            AirQualityStation,
            str,
            dict[PollutantCode, tuple[float, str]],
            datetime | None,
            bool,
        ]
    ]:
        stmt = (
            select(AirQualityStation, AirQualitySource.slug)
            .join(AirQualitySource, AirQualitySource.id == AirQualityStation.source_id)
            .where(
                AirQualityStation.is_active.is_(True),
                AirQualityStation.latitude >= min_lat,
                AirQualityStation.latitude <= max_lat,
                AirQualityStation.longitude >= min_lon,
                AirQualityStation.longitude <= max_lon,
            )
            .limit(100)
        )
        rows = (await self._session.execute(stmt)).all()
        if not rows:
            return []

        station_ids = [station.id for station, _ in rows]
        latest_subq = (
            select(
                AirQualityMeasurement.station_id.label("station_id"),
                func.max(AirQualityMeasurement.measured_at).label("latest_measured_at"),
            )
            .where(AirQualityMeasurement.station_id.in_(station_ids))
            .group_by(AirQualityMeasurement.station_id)
            .subquery()
        )
        m_stmt = select(AirQualityMeasurement).join(
            latest_subq,
            (AirQualityMeasurement.station_id == latest_subq.c.station_id)
            & (AirQualityMeasurement.measured_at == latest_subq.c.latest_measured_at),
        )
        latest_measurements = (await self._session.execute(m_stmt)).scalars().all()

        latest_ts_by_station: dict[uuid.UUID, datetime] = {}
        measurements_by_station: dict[uuid.UUID, dict[PollutantCode, tuple[float, str]]] = {}
        fixture_stations: set[uuid.UUID] = set()
        for m_row in latest_measurements:
            latest_ts_by_station[m_row.station_id] = m_row.measured_at
            bucket = measurements_by_station.setdefault(m_row.station_id, {})
            if m_row.pollutant in PollutantCode._value2member_map_:
                p_code = PollutantCode(m_row.pollutant)
                bucket[p_code] = (float(m_row.concentration), m_row.unit)
            if m_row.quality_flag == "development_fixture":
                fixture_stations.add(m_row.station_id)

        results: list[
            tuple[
                AirQualityStation,
                str,
                dict[PollutantCode, tuple[float, str]],
                datetime | None,
                bool,
            ]
        ] = []
        for station, provider_slug in rows:
            is_fixture = provider_slug == "development_fixture" or station.id in fixture_stations
            results.append(
                (
                    station,
                    provider_slug,
                    measurements_by_station.get(station.id, {}),
                    latest_ts_by_station.get(station.id),
                    is_fixture,
                )
            )

        return results
