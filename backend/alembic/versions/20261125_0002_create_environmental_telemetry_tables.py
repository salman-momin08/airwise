"""Create environmental telemetry sources, stations, measurements, forecasts, and weather tables.

Revision ID: 20261125_0002
Revises: 20261124_0001
Create Date: 2026-11-25 00:35:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from geoalchemy2 import Geography
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261125_0002"
down_revision: str | None = "20261124_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    is_pg = _is_postgresql()
    json_type: sa.types.TypeEngine[object] = postgresql.JSONB() if is_pg else sa.JSON()
    coordinates_type: sa.types.TypeEngine[object] = (
        Geography(geometry_type="POINT", srid=4326) if is_pg else sa.Text()
    )

    op.create_table(
        "air_quality_sources",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("provider_type", sa.String(length=64), nullable=False),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column(
            "refresh_interval_seconds",
            sa.Integer(),
            nullable=False,
            server_default="900",
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true") if is_pg else sa.text("1"),
        ),
        sa.Column("priority_rank", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_air_quality_sources_slug", "air_quality_sources", ["slug"], unique=True)

    op.create_table(
        "air_quality_stations",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "source_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("air_quality_sources.id"),
            nullable=False,
        ),
        sa.Column("external_station_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("state_region", sa.String(length=120), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=False, server_default="IN"),
        sa.Column("coordinates", coordinates_type, nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="station"),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true") if is_pg else sa.text("1"),
        ),
        sa.UniqueConstraint(
            "source_id",
            "external_station_id",
            name="uq_aq_stations_source_external_id",
        ),
    )
    op.create_index(
        "ix_aq_stations_city_active",
        "air_quality_stations",
        ["city", "is_active"],
        unique=False,
    )
    if is_pg:
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_aq_stations_coordinates_gist "
            "ON air_quality_stations USING GIST (coordinates)"
        )

    measurement_kwargs: dict[str, str] = (
        {"postgresql_partition_by": "RANGE (measured_at)"} if is_pg else {}
    )
    op.create_table(
        "air_quality_measurements",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), primary_key=True, nullable=False),
        sa.Column(
            "station_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("air_quality_stations.id"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("air_quality_sources.id"),
            nullable=False,
        ),
        sa.Column("pollutant", sa.String(length=16), nullable=False),
        sa.Column("concentration", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column(
            "averaging_period_hours",
            sa.SmallInteger(),
            nullable=False,
            server_default="24",
        ),
        sa.Column(
            "source_timezone",
            sa.String(length=64),
            nullable=False,
            server_default="Asia/Kolkata",
        ),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quality_flag", sa.String(length=32), nullable=False, server_default="verified"),
        **measurement_kwargs,
    )
    if is_pg:
        op.execute(
            "CREATE TABLE IF NOT EXISTS air_quality_measurements_2026_11 "
            "PARTITION OF air_quality_measurements "
            "FOR VALUES FROM ('2026-11-01 00:00:00+00') TO ('2026-12-01 00:00:00+00')"
        )
        op.execute(
            "CREATE TABLE IF NOT EXISTS air_quality_measurements_2026_12 "
            "PARTITION OF air_quality_measurements "
            "FOR VALUES FROM ('2026-12-01 00:00:00+00') TO ('2027-01-01 00:00:00+00')"
        )
        op.execute(
            "CREATE TABLE IF NOT EXISTS air_quality_measurements_default "
            "PARTITION OF air_quality_measurements DEFAULT"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_aq_measurements_station_pollutant_measured "
            "ON air_quality_measurements (station_id, pollutant, measured_at DESC)"
        )
    else:
        op.create_index(
            "ix_aq_measurements_station_pollutant_measured",
            "air_quality_measurements",
            ["station_id", "pollutant", "measured_at"],
            unique=False,
        )

    op.create_table(
        "air_quality_forecasts",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "source_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("air_quality_sources.id"),
            nullable=False,
        ),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("coordinates", coordinates_type, nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("forecast_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pollutants", json_type, nullable=False),
        sa.Column(
            "confidence_level",
            sa.String(length=32),
            nullable=False,
            server_default="medium",
        ),
        sa.Column(
            "is_development_fixture",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false") if is_pg else sa.text("0"),
        ),
    )
    op.create_index(
        "ix_aq_forecasts_city_forecast_for",
        "air_quality_forecasts",
        ["city", "forecast_for"],
        unique=False,
    )

    op.create_table(
        "weather_observations",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("coordinates", coordinates_type, nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("temperature_c", sa.Float(), nullable=False),
        sa.Column("humidity_pct", sa.Float(), nullable=False),
        sa.Column("wind_speed_mps", sa.Float(), nullable=False),
        sa.Column("wind_direction_deg", sa.Integer(), nullable=True),
        sa.Column("inversion_risk_flag", sa.Boolean(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column(
            "is_stale",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false") if is_pg else sa.text("0"),
        ),
        sa.Column(
            "is_development_fixture",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false") if is_pg else sa.text("0"),
        ),
    )
    op.create_index(
        "ix_weather_observations_city_observed",
        "weather_observations",
        ["city", "observed_at"],
        unique=False,
    )


def downgrade() -> None:
    is_pg = _is_postgresql()

    op.drop_index("ix_weather_observations_city_observed", table_name="weather_observations")
    op.drop_table("weather_observations")

    op.drop_index("ix_aq_forecasts_city_forecast_for", table_name="air_quality_forecasts")
    op.drop_table("air_quality_forecasts")

    if is_pg:
        op.execute("DROP TABLE IF EXISTS air_quality_measurements CASCADE")
    else:
        op.drop_index(
            "ix_aq_measurements_station_pollutant_measured",
            table_name="air_quality_measurements",
        )
        op.drop_table("air_quality_measurements")

    if is_pg:
        op.execute("DROP INDEX IF EXISTS ix_aq_stations_coordinates_gist")
    op.drop_index("ix_aq_stations_city_active", table_name="air_quality_stations")
    op.drop_table("air_quality_stations")

    op.drop_index("ix_air_quality_sources_slug", table_name="air_quality_sources")
    op.drop_table("air_quality_sources")
