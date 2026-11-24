"""Create identity, session, preference, saved location, and audit tables.

Revision ID: 20261124_0001
Revises: None
Create Date: 2026-11-24 23:45:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography
from sqlalchemy.dialects import postgresql

revision: str = "20261124_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    is_pg = _is_postgresql()
    if is_pg:
        op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
        op.execute('CREATE EXTENSION IF NOT EXISTS "citext"')
        op.execute('CREATE EXTENSION IF NOT EXISTS "postgis"')

    email_type: sa.types.TypeEngine[object] = (
        postgresql.CITEXT() if is_pg else sa.String(length=320)
    )
    json_type: sa.types.TypeEngine[object] = postgresql.JSONB() if is_pg else sa.JSON()
    coordinates_type: sa.types.TypeEngine[object] = (
        Geography(geometry_type="POINT", srid=4326) if is_pg else sa.Text()
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", email_type, nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="user"),
        sa.Column(
            "is_email_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false") if is_pg else sa.text("0"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true") if is_pg else sa.text("1"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "user_profiles",
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("locale", sa.String(length=16), nullable=False, server_default="en"),
        sa.Column(
            "preferred_aqi_standard",
            sa.String(length=32),
            nullable=False,
            server_default="india_naqi",
        ),
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default="Asia/Kolkata",
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("refresh_token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("csrf_secret_hash", sa.Text(), nullable=False),
        sa.Column("ip_hash", sa.String(length=128), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_user_sessions_user_id_revoked_at",
        "user_sessions",
        ["user_id", "revoked_at"],
        unique=False,
    )

    op.create_table(
        "user_preferences",
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("age_category", sa.String(length=32), nullable=True),
        sa.Column("household_size", sa.Integer(), nullable=True),
        sa.Column("has_vulnerable_members", sa.Boolean(), nullable=True),
        sa.Column("work_schedule", json_type, nullable=True),
        sa.Column("school_schedule", json_type, nullable=True),
        sa.Column("commute_modes", json_type, nullable=False),
        sa.Column("cooking_type", sa.String(length=64), nullable=True),
        sa.Column("ventilation_type", sa.String(length=64), nullable=True),
        sa.Column(
            "has_hepa_purifier",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false") if is_pg else sa.text("0"),
        ),
        sa.Column("budget_tier", sa.String(length=32), nullable=True),
        sa.Column("sustainability_goals", json_type, nullable=False),
        sa.Column(
            "save_chat_history",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true") if is_pg else sa.text("1"),
        ),
        sa.Column("consent_updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "saved_locations",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("label", sa.String(length=32), nullable=False, server_default="home"),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("state_region", sa.String(length=120), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=False, server_default="IN"),
        sa.Column("postal_code", sa.String(length=32), nullable=True),
        sa.Column("coordinates", coordinates_type, nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column(
            "location_precision",
            sa.String(length=32),
            nullable=False,
            server_default="city",
        ),
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default="Asia/Kolkata",
        ),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false") if is_pg else sa.text("0"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_saved_locations_user_id", "saved_locations", ["user_id"], unique=False)
    op.create_index(
        "uq_saved_locations_user_primary",
        "saved_locations",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_primary = true"),
        sqlite_where=sa.text("is_primary = 1"),
    )
    if is_pg:
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_saved_locations_coordinates_gist "
            "ON saved_locations USING GIST (coordinates)"
        )

    op.create_table(
        "user_action_tokens",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_user_action_tokens_user_purpose",
        "user_action_tokens",
        ["user_id", "purpose"],
        unique=False,
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "actor_user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=96), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=True),
        sa.Column("metadata_redacted", json_type, nullable=False),
        sa.Column("ip_hash", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_audit_logs_actor_created",
        "audit_logs",
        ["actor_user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    is_pg = _is_postgresql()
    op.drop_index("ix_audit_logs_actor_created", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_user_action_tokens_user_purpose", table_name="user_action_tokens")
    op.drop_table("user_action_tokens")

    if is_pg:
        op.execute("DROP INDEX IF EXISTS ix_saved_locations_coordinates_gist")
    op.drop_index("uq_saved_locations_user_primary", table_name="saved_locations")
    op.drop_index("ix_saved_locations_user_id", table_name="saved_locations")
    op.drop_table("saved_locations")

    op.drop_table("user_preferences")

    op.drop_index("ix_user_sessions_user_id_revoked_at", table_name="user_sessions")
    op.drop_table("user_sessions")

    op.drop_table("user_profiles")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
