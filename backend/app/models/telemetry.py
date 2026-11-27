"""ORM entities for air quality data sources, monitoring stations, measurements, and weather."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

JSON_VARIANT = JSON().with_variant(JSONB(), "postgresql")
GEOGRAPHY_POINT_VARIANT = Text().with_variant(
    Geography(geometry_type="POINT", srid=4326),
    "postgresql",
)


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


class AirQualitySource(Base):
    __tablename__ = "air_quality_sources"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(64), nullable=False)
    license_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=900)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class AirQualityStation(Base):
    __tablename__ = "air_quality_stations"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "external_station_id",
            name="uq_aq_stations_source_external_id",
        ),
        Index("ix_aq_stations_city_active", "city", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("air_quality_sources.id"), nullable=False
    )
    external_station_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    state_region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, default="IN")
    coordinates: Mapped[Any | None] = mapped_column(GEOGRAPHY_POINT_VARIANT, nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="station")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AirQualityMeasurement(Base):
    """Immutable pollutant measurement row (monthly UTC range-partitioned on PostgreSQL)."""

    __tablename__ = "air_quality_measurements"
    __table_args__ = (
        Index(
            "ix_aq_measurements_station_pollutant_measured",
            "station_id",
            "pollutant",
            "measured_at",
        ),
        {"postgresql_partition_by": "RANGE (measured_at)"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    station_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("air_quality_stations.id"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("air_quality_sources.id"), nullable=False
    )
    pollutant: Mapped[str] = mapped_column(String(16), nullable=False)
    concentration: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    averaging_period_hours: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=24)
    source_timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Kolkata")
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    quality_flag: Mapped[str] = mapped_column(String(32), nullable=False, default="verified")


class AirQualityForecast(Base):
    __tablename__ = "air_quality_forecasts"
    __table_args__ = (Index("ix_aq_forecasts_city_forecast_for", "city", "forecast_for"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("air_quality_sources.id"), nullable=False
    )
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    coordinates: Mapped[Any | None] = mapped_column(GEOGRAPHY_POINT_VARIANT, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    forecast_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    pollutants: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False)
    confidence_level: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    is_development_fixture: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class WeatherObservation(Base):
    __tablename__ = "weather_observations"
    __table_args__ = (Index("ix_weather_observations_city_observed", "city", "observed_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    coordinates: Mapped[Any | None] = mapped_column(GEOGRAPHY_POINT_VARIANT, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_c: Mapped[float] = mapped_column(Float, nullable=False)
    humidity_pct: Mapped[float] = mapped_column(Float, nullable=False)
    wind_speed_mps: Mapped[float] = mapped_column(Float, nullable=False)
    wind_direction_deg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inversion_risk_flag: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    is_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_development_fixture: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
