"""Create emission factors, user actions, impact estimates, routines, and recommendations tables.

Revision ID: 20261126_0004
Revises: 20261126_0003
Create Date: 2026-11-26 20:50:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261126_0004"
down_revision: str | None = "20261126_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    is_pg = op.get_bind().dialect.name == "postgresql"
    json_type: sa.types.TypeEngine[object] = postgresql.JSONB() if is_pg else sa.JSON()
    bool_true = sa.text("true") if is_pg else sa.text("1")
    bool_false = sa.text("false") if is_pg else sa.text("0")

    op.create_table(
        "emission_factors",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("mode_or_region_code", sa.String(length=96), nullable=False, unique=True),
        sa.Column("display_label", sa.String(length=160), nullable=False),
        sa.Column("factor_value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("default_occupancy", sa.Float(), nullable=True),
        sa.Column("exposure_modifier", sa.Float(), nullable=True),
        sa.Column("source_reference", sa.String(length=300), nullable=False),
        sa.Column("effective_year", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=bool_true),
    )
    op.create_index("ix_emission_factors_category", "emission_factors", ["category"])

    op.create_table(
        "user_actions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_self_reported", sa.Boolean(), nullable=False, server_default=bool_true),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_actions_user_occurred", "user_actions", ["user_id", "occurred_at"])

    op.create_table(
        "impact_estimates",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "user_action_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("user_actions.id"),
            nullable=True,
        ),
        sa.Column("metric", sa.String(length=48), nullable=False),
        sa.Column("baseline_value", sa.Float(), nullable=False),
        sa.Column("alternative_value", sa.Float(), nullable=False),
        sa.Column("estimated_difference", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=48), nullable=False),
        sa.Column("methodology", sa.String(length=96), nullable=False),
        sa.Column("assumptions", json_type, nullable=False),
        sa.Column("source_references", json_type, nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("is_estimate", sa.Boolean(), nullable=False, server_default=bool_true),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("is_estimate = true", name="ck_impact_estimates_is_estimate_true"),
    )
    op.create_index(
        "ix_impact_estimates_user_calculated",
        "impact_estimates",
        ["user_id", "calculated_at"],
    )

    op.create_table(
        "daily_routines",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "location_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("saved_locations.id"),
            nullable=True,
        ),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("aqi_standard", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("environmental_snapshot_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("environmental_summary", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_daily_routines_user_plan_date", "daily_routines", ["user_id", "plan_date"])

    op.create_table(
        "routine_activities",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "routine_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("daily_routines.id"),
            nullable=False,
        ),
        sa.Column("slot_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("time_block", sa.String(length=32), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("environment_type", sa.String(length=32), nullable=False),
        sa.Column("exposure_note", sa.Text(), nullable=False),
        sa.Column("safer_alternative", sa.Text(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("safety_warning", sa.Text(), nullable=True),
        sa.Column(
            "impact_estimate_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("impact_estimates.id"),
            nullable=True,
        ),
        sa.Column("confidence", sa.String(length=16), nullable=False, server_default="medium"),
    )
    op.create_index("ix_routine_activities_routine_id", "routine_activities", ["routine_id"])

    op.create_table(
        "recommendations",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("aqi_standard", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=48), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("action_steps", json_type, nullable=False),
        sa.Column("safer_alternative", sa.Text(), nullable=True),
        sa.Column("uncertainty_note", sa.Text(), nullable=False),
        sa.Column(
            "impact_estimate_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("impact_estimates.id"),
            nullable=True,
        ),
        sa.Column("evidence_document_ids", json_type, nullable=False),
        sa.Column("is_ai_enriched", sa.Boolean(), nullable=False, server_default=bool_false),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_recommendations_user_valid_until",
        "recommendations",
        ["user_id", "valid_until"],
    )

    op.create_table(
        "recommendation_feedback",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "recommendation_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("recommendations.id"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_recommendation_feedback_rec_user",
        "recommendation_feedback",
        ["recommendation_id", "user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_recommendation_feedback_rec_user", table_name="recommendation_feedback")
    op.drop_table("recommendation_feedback")
    op.drop_index("ix_recommendations_user_valid_until", table_name="recommendations")
    op.drop_table("recommendations")
    op.drop_index("ix_routine_activities_routine_id", table_name="routine_activities")
    op.drop_table("routine_activities")
    op.drop_index("ix_daily_routines_user_plan_date", table_name="daily_routines")
    op.drop_table("daily_routines")
    op.drop_index("ix_impact_estimates_user_calculated", table_name="impact_estimates")
    op.drop_table("impact_estimates")
    op.drop_index("ix_user_actions_user_occurred", table_name="user_actions")
    op.drop_table("user_actions")
    op.drop_index("ix_emission_factors_category", table_name="emission_factors")
    op.drop_table("emission_factors")
