"""Pydantic v2 DTOs for smart AQI alert rules, quiet hours, and notification deliveries."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.air_quality.aqi_calculator import AQIStandard

AlertTypeLiteral = Literal[
    "aqi_threshold",
    "severe_smog_episode",
    "forecast_deterioration",
    "clean_air_window",
    "stale_telemetry_warning",
    "daily_digest",
]
AlertChannelLiteral = Literal["in_app", "email", "web_push"]
NotificationSeverityLiteral = Literal["info", "warning", "critical"]
DeliveryStatusLiteral = Literal[
    "pending",
    "sent",
    "failed",
    "suppressed_quiet_hours",
    "unconfigured_channel",
]

HHMM_PATTERN = r"^(?:[01]\d|2[0-3]):[0-5]\d$"


def _validate_iana_timezone(tz_name: str) -> str:
    cleaned = tz_name.strip()
    try:
        ZoneInfo(cleaned)
    except (ZoneInfoNotFoundError, KeyError) as exc:
        raise ValueError(f"Unknown IANA timezone '{cleaned}'.") from exc
    return cleaned


def _default_alert_channels() -> list[AlertChannelLiteral]:
    return ["in_app"]


class CreateAlertRuleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    city: str = Field(min_length=2, max_length=100, pattern=r"^[\w .'-]+$")
    location_id: UUID | None = None
    alert_type: AlertTypeLiteral = "aqi_threshold"
    aqi_standard: AQIStandard = AQIStandard.INDIA_NAQI
    threshold_value: int | None = Field(default=200, ge=10, le=500)
    channels: list[AlertChannelLiteral] = Field(
        default_factory=_default_alert_channels, min_length=1, max_length=3
    )
    quiet_hours_start: str | None = Field(default=None, pattern=HHMM_PATTERN)
    quiet_hours_end: str | None = Field(default=None, pattern=HHMM_PATTERN)
    cooldown_minutes: int = Field(default=180, ge=15, le=1440)
    timezone: str = Field(default="Asia/Kolkata", min_length=2, max_length=64)
    is_enabled: bool = True

    @field_validator("timezone")
    @classmethod
    def check_timezone(cls, value: str) -> str:
        return _validate_iana_timezone(value)

    @model_validator(mode="after")
    def check_quiet_hours_and_threshold(self) -> Self:
        if (self.quiet_hours_start is None) != (self.quiet_hours_end is None):
            raise ValueError(
                "Provide both quiet_hours_start and quiet_hours_end together, or omit both."
            )
        if self.alert_type == "aqi_threshold" and self.threshold_value is None:
            raise ValueError("threshold_value is required when alert_type is 'aqi_threshold'.")
        return self


class UpdateAlertRuleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    threshold_value: int | None = Field(default=None, ge=10, le=500)
    channels: list[AlertChannelLiteral] | None = Field(default=None, min_length=1, max_length=3)
    quiet_hours_start: str | None = Field(default=None, pattern=HHMM_PATTERN)
    quiet_hours_end: str | None = Field(default=None, pattern=HHMM_PATTERN)
    clear_quiet_hours: bool = False
    cooldown_minutes: int | None = Field(default=None, ge=15, le=1440)
    timezone: str | None = Field(default=None, min_length=2, max_length=64)
    is_enabled: bool | None = None

    @field_validator("timezone")
    @classmethod
    def check_optional_timezone(cls, value: str | None) -> str | None:
        return _validate_iana_timezone(value) if value is not None else None

    @model_validator(mode="after")
    def check_optional_quiet_hours(self) -> Self:
        if (self.quiet_hours_start is None) != (self.quiet_hours_end is None):
            raise ValueError(
                "Provide both quiet_hours_start and quiet_hours_end together when updating."
            )
        return self


class AlertRuleSchema(BaseModel):
    id: UUID
    location_id: UUID | None = None
    city: str
    alert_type: AlertTypeLiteral
    aqi_standard: AQIStandard
    threshold_value: int | None = None
    channels: list[AlertChannelLiteral]
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    cooldown_minutes: int
    timezone: str
    is_enabled: bool
    last_triggered_at: datetime | None = None
    created_at: datetime


class NotificationDeliverySchema(BaseModel):
    id: UUID
    channel: AlertChannelLiteral
    status: DeliveryStatusLiteral
    provider_message_id: str | None = None
    attempt_count: int
    delivered_at: datetime | None = None


class NotificationSchema(BaseModel):
    id: UUID
    alert_rule_id: UUID | None = None
    title: str
    body: str
    severity: NotificationSeverityLiteral
    dedup_key: str
    read_at: datetime | None = None
    created_at: datetime
    deliveries: list[NotificationDeliverySchema] = Field(default_factory=list)


class AlertEvaluationSummarySchema(BaseModel):
    evaluated_rules: int
    triggered_notifications: int
    suppressed_duplicates_or_cooldown: int
    suppressed_quiet_hours_deliveries: int
