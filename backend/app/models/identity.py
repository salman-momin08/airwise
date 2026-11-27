"""ORM entities for users, profiles, preferences, sessions, saved locations, and audit logs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.db.base import Base

JSON_VARIANT = JSON().with_variant(JSONB(), "postgresql")
CITEXT_VARIANT = String(320).with_variant(CITEXT(), "postgresql")
GEOGRAPHY_POINT_VARIANT = Text().with_variant(
    Geography(geometry_type="POINT", srid=4326),
    "postgresql",
)


class StringListType(TypeDecorator[list[str]]):
    """Cross-dialect list[str] stored as JSONB/JSON for PostgreSQL & SQLite test parity."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(CITEXT_VARIANT, unique=True, nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    is_email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    profile: Mapped[UserProfile | None] = relationship(
        "UserProfile", back_populates="user", uselist=False
    )
    preferences: Mapped[UserPreference | None] = relationship(
        "UserPreference", back_populates="user", uselist=False
    )


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    preferred_aqi_standard: Mapped[str] = mapped_column(
        String(32), nullable=False, default="india_naqi"
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Kolkata")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    user: Mapped[User] = relationship("User", back_populates="profile")


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (Index("ix_user_sessions_user_id_revoked_at", "user_id", "revoked_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    refresh_token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    csrf_secret_hash: Mapped[str] = mapped_column(Text, nullable=False)
    ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    age_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    household_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_vulnerable_members: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    work_schedule: Mapped[dict[str, Any] | None] = mapped_column(JSON_VARIANT, nullable=True)
    school_schedule: Mapped[dict[str, Any] | None] = mapped_column(JSON_VARIANT, nullable=True)
    commute_modes: Mapped[list[str]] = mapped_column(StringListType, nullable=False, default=list)
    cooking_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ventilation_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    has_hepa_purifier: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    budget_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sustainability_goals: Mapped[list[str]] = mapped_column(
        StringListType, nullable=False, default=list
    )
    save_chat_history: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    consent_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship("User", back_populates="preferences")


class SavedLocation(Base):
    __tablename__ = "saved_locations"
    __table_args__ = (
        Index("ix_saved_locations_user_id", "user_id"),
        Index(
            "uq_saved_locations_user_primary",
            "user_id",
            unique=True,
            postgresql_where=text("is_primary = true"),
            sqlite_where=text("is_primary = 1"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(32), nullable=False, default="home")
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    state_region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, default="IN")
    postal_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    coordinates: Mapped[Any | None] = mapped_column(GEOGRAPHY_POINT_VARIANT, nullable=True)
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)
    location_precision: Mapped[str] = mapped_column(String(32), nullable=False, default="city")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Kolkata")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class UserActionToken(Base):
    """Single-use hashed tokens for email verification and password reset."""

    __tablename__ = "user_action_tokens"
    __table_args__ = (Index("ix_user_action_tokens_user_purpose", "user_id", "purpose"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_actor_created", "actor_user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(96), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_redacted: Mapped[dict[str, Any]] = mapped_column(
        JSON_VARIANT, nullable=False, default=dict
    )
    ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(96), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, nullable=False, default=dict)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
