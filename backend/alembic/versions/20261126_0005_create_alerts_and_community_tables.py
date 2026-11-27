"""Create alert rules, notifications, deliveries, communities, initiatives, and reports tables.

Revision ID: 20261126_0005
Revises: 20261126_0004
Create Date: 2026-11-26 21:50:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261126_0005"
down_revision: str | None = "20261126_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    is_pg = op.get_bind().dialect.name == "postgresql"
    json_type: sa.types.TypeEngine[object] = postgresql.JSONB() if is_pg else sa.JSON()
    bool_true = sa.text("true") if is_pg else sa.text("1")
    bool_false = sa.text("false") if is_pg else sa.text("0")

    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "location_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("saved_locations.id"),
            nullable=True,
        ),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("alert_type", sa.String(length=48), nullable=False),
        sa.Column("aqi_standard", sa.String(length=32), nullable=False),
        sa.Column("threshold_value", sa.Integer(), nullable=True),
        sa.Column("channels", json_type, nullable=False),
        sa.Column("quiet_hours_start", sa.Time(), nullable=True),
        sa.Column("quiet_hours_end", sa.Time(), nullable=True),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False, server_default="180"),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Asia/Kolkata"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=bool_true),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_dedup_state", sa.String(length=180), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_alert_rules_user_enabled", "alert_rules", ["user_id", "is_enabled"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "alert_rule_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("alert_rules.id"),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=24), nullable=False, server_default="warning"),
        sa.Column("dedup_key", sa.String(length=180), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", "created_at"])
    op.create_index("ix_notifications_user_dedup", "notifications", ["user_id", "dedup_key"])

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "notification_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("notifications.id"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=36), nullable=False, server_default="pending"),
        sa.Column("provider_message_id", sa.String(length=160), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_notification_deliveries_notif_id",
        "notification_deliveries",
        ["notification_id"],
    )

    op.create_table(
        "communities",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(length=96), nullable=False, unique=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("coarse_boundary_label", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("moderation_policy", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_communities_slug", "communities", ["slug"], unique=True)
    op.create_index("ix_communities_city", "communities", ["city"])

    op.create_table(
        "community_members",
        sa.Column(
            "community_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("communities.id"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("role", sa.String(length=24), nullable=False, server_default="member"),
        sa.Column(
            "public_display_consent",
            sa.Boolean(),
            nullable=False,
            server_default=bool_false,
        ),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_community_members_user_id", "community_members", ["user_id"])

    op.create_table(
        "community_initiatives",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "community_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("communities.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("challenge_type", sa.String(length=48), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "moderation_status", sa.String(length=24), nullable=False, server_default="active"
        ),
        sa.Column("created_by", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_community_initiatives_comm_status",
        "community_initiatives",
        ["community_id", "moderation_status"],
    )

    op.create_table(
        "community_participation",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "initiative_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("community_initiatives.id"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("self_reported_actions_count", sa.Integer(), nullable=False),
        sa.Column("estimated_avoided_co2e_kg", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("note", sa.String(length=280), nullable=True),
        sa.Column(
            "moderation_status", sa.String(length=24), nullable=False, server_default="approved"
        ),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_community_participation_initiative",
        "community_participation",
        ["initiative_id"],
    )

    op.create_table(
        "community_abuse_reports",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "community_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("communities.id"),
            nullable=False,
        ),
        sa.Column(
            "initiative_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("community_initiatives.id"),
            nullable=True,
        ),
        sa.Column(
            "reporter_user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("reason_category", sa.String(length=48), nullable=False),
        sa.Column("details", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("resolved_by", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolution_note", sa.String(length=400), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_community_abuse_reports_status",
        "community_abuse_reports",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_community_abuse_reports_status", table_name="community_abuse_reports")
    op.drop_table("community_abuse_reports")
    op.drop_index("ix_community_participation_initiative", table_name="community_participation")
    op.drop_table("community_participation")
    op.drop_index("ix_community_initiatives_comm_status", table_name="community_initiatives")
    op.drop_table("community_initiatives")
    op.drop_index("ix_community_members_user_id", table_name="community_members")
    op.drop_table("community_members")
    op.drop_index("ix_communities_city", table_name="communities")
    op.drop_index("ix_communities_slug", table_name="communities")
    op.drop_table("communities")
    op.drop_index("ix_notification_deliveries_notif_id", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")
    op.drop_index("ix_notifications_user_dedup", table_name="notifications")
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_alert_rules_user_enabled", table_name="alert_rules")
    op.drop_table("alert_rules")
