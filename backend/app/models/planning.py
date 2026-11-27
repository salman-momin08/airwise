"""ORM entities for daily routines, recommendations, emission factors, and impact estimates."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.identity import JSON_VARIANT, StringListType, utc_now


class EmissionFactor(Base):
    __tablename__ = "emission_factors"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    mode_or_region_code: Mapped[str] = mapped_column(String(96), nullable=False, unique=True)
    display_label: Mapped[str] = mapped_column(String(160), nullable=False)
    factor_value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    default_occupancy: Mapped[float | None] = mapped_column(Float, nullable=True)
    exposure_modifier: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_reference: Mapped[str] = mapped_column(String(300), nullable=False)
    effective_year: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class UserAction(Base):
    __tablename__ = "user_actions"
    __table_args__ = (Index("ix_user_actions_user_occurred", "user_id", "occurred_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    is_self_reported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    estimates: Mapped[list[ImpactEstimate]] = relationship(
        "ImpactEstimate", back_populates="user_action"
    )


class ImpactEstimate(Base):
    __tablename__ = "impact_estimates"
    __table_args__ = (
        CheckConstraint("is_estimate = true", name="ck_impact_estimates_is_estimate_true"),
        Index("ix_impact_estimates_user_calculated", "user_id", "calculated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    user_action_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user_actions.id"), nullable=True
    )
    metric: Mapped[str] = mapped_column(String(48), nullable=False)
    baseline_value: Mapped[float] = mapped_column(Float, nullable=False)
    alternative_value: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_difference: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(48), nullable=False)
    methodology: Mapped[str] = mapped_column(String(96), nullable=False)
    assumptions: Mapped[list[str]] = mapped_column(StringListType, nullable=False, default=list)
    source_references: Mapped[list[str]] = mapped_column(
        StringListType, nullable=False, default=list
    )
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    is_estimate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    user_action: Mapped[UserAction | None] = relationship("UserAction", back_populates="estimates")


class DailyRoutine(Base):
    __tablename__ = "daily_routines"
    __table_args__ = (Index("ix_daily_routines_user_plan_date", "user_id", "plan_date"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("saved_locations.id"), nullable=True
    )
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    aqi_standard: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    environmental_snapshot_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    environmental_summary: Mapped[dict[str, Any] | None] = mapped_column(
        JSON_VARIANT, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    activities: Mapped[list[RoutineActivity]] = relationship(
        "RoutineActivity",
        back_populates="routine",
        order_by="RoutineActivity.slot_order",
    )


class RoutineActivity(Base):
    __tablename__ = "routine_activities"
    __table_args__ = (Index("ix_routine_activities_routine_id", "routine_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    routine_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("daily_routines.id"), nullable=False
    )
    slot_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    time_block: Mapped[str] = mapped_column(String(32), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    environment_type: Mapped[str] = mapped_column(String(32), nullable=False)
    exposure_note: Mapped[str] = mapped_column(Text, nullable=False)
    safer_alternative: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    safety_warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    impact_estimate_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("impact_estimates.id"), nullable=True
    )
    confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")

    routine: Mapped[DailyRoutine] = relationship("DailyRoutine", back_populates="activities")


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (Index("ix_recommendations_user_valid_until", "user_id", "valid_until"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    aqi_standard: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(48), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    action_steps: Mapped[list[str]] = mapped_column(StringListType, nullable=False, default=list)
    safer_alternative: Mapped[str | None] = mapped_column(Text, nullable=True)
    uncertainty_note: Mapped[str] = mapped_column(Text, nullable=False)
    impact_estimate_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("impact_estimates.id"), nullable=True
    )
    evidence_document_ids: Mapped[list[str]] = mapped_column(
        StringListType, nullable=False, default=list
    )
    is_ai_enriched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    feedback_entries: Mapped[list[RecommendationFeedback]] = relationship(
        "RecommendationFeedback", back_populates="recommendation"
    )


class RecommendationFeedback(Base):
    __tablename__ = "recommendation_feedback"
    __table_args__ = (Index("ix_recommendation_feedback_rec_user", "recommendation_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("recommendations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    recommendation: Mapped[Recommendation] = relationship(
        "Recommendation", back_populates="feedback_entries"
    )
