from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

AQIStandardLiteral = Literal["india_naqi", "us_epa"]
LocationLabelLiteral = Literal["home", "workplace", "school", "other"]
LocationPrecisionLiteral = Literal["city", "postal_code", "neighborhood", "exact"]
AgeCategoryLiteral = Literal["youth", "adult", "older_adult", "prefer_not_to_say"]
BudgetTierLiteral = Literal["low", "moderate", "flexible"]
CommuteModeLiteral = Literal[
    "walk",
    "bicycle",
    "two_wheeler_petrol",
    "two_wheeler_ev",
    "car_solo_petrol",
    "car_ev",
    "carpool_3",
    "bus",
    "metro_rail",
    "work_from_home",
]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=2, max_length=120)
    preferred_aqi_standard: AQIStandardLiteral = "india_naqi"
    timezone: str = Field(default="Asia/Kolkata", min_length=2, max_length=64)
    locale: str = Field(default="en", min_length=2, max_length=16)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        has_alpha = any(ch.isalpha() for ch in value)
        has_digit = any(ch.isdigit() for ch in value)
        if not (has_alpha and has_digit):
            raise ValueError("Password must include at least one letter and one number.")
        return value

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("Display name must be at least 2 characters.")
        return cleaned


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    new_password: str = Field(min_length=10, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(cls, value: str) -> str:
        has_alpha = any(ch.isalpha() for ch in value)
        has_digit = any(ch.isdigit() for ch in value)
        if not (has_alpha and has_digit):
            raise ValueError("Password must include at least one letter and one number.")
        return value


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)


class AuthPrincipalData(BaseModel):
    user_id: str | None
    email: str | None = None
    display_name: str | None = None
    role: str
    is_email_verified: bool = False
    preferred_aqi_standard: AQIStandardLiteral = "india_naqi"
    session_id: str | None = None


class SessionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_agent: str | None = None
    created_at: datetime
    expires_at: datetime
    is_current: bool = False


class TimeWindowSchedule(BaseModel):
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    days: list[str] = Field(default_factory=list, max_length=7)


class UserProfileData(BaseModel):
    display_name: str
    locale: str
    preferred_aqi_standard: AQIStandardLiteral
    timezone: str
    updated_at: datetime


class UserPreferencesData(BaseModel):
    age_category: AgeCategoryLiteral | None = None
    household_size: int | None = None
    has_vulnerable_members: bool | None = None
    work_schedule: TimeWindowSchedule | None = None
    school_schedule: TimeWindowSchedule | None = None
    commute_modes: list[CommuteModeLiteral] = Field(default_factory=list)
    cooking_type: str | None = None
    ventilation_type: str | None = None
    has_hepa_purifier: bool = False
    budget_tier: BudgetTierLiteral | None = None
    sustainability_goals: list[str] = Field(default_factory=list)
    save_chat_history: bool = True
    consent_updated_at: datetime | None = None


class UserMeData(BaseModel):
    id: UUID
    email: str
    role: str
    is_email_verified: bool
    created_at: datetime
    profile: UserProfileData
    preferences: UserPreferencesData


class UpdateUserProfileInput(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=120)
    locale: str | None = Field(default=None, min_length=2, max_length=16)
    preferred_aqi_standard: AQIStandardLiteral | None = None
    timezone: str | None = Field(default=None, min_length=2, max_length=64)


class UpdateUserPreferencesInput(BaseModel):
    age_category: AgeCategoryLiteral | None = None
    household_size: int | None = Field(default=None, ge=1, le=20)
    has_vulnerable_members: bool | None = None
    work_schedule: TimeWindowSchedule | None = None
    school_schedule: TimeWindowSchedule | None = None
    commute_modes: list[CommuteModeLiteral] | None = Field(default=None, max_length=10)
    cooking_type: str | None = Field(default=None, max_length=64)
    ventilation_type: str | None = Field(default=None, max_length=64)
    has_hepa_purifier: bool | None = None
    budget_tier: BudgetTierLiteral | None = None
    sustainability_goals: list[str] | None = Field(default=None, max_length=10)
    save_chat_history: bool | None = None


class UpdateUserMeRequest(BaseModel):
    profile: UpdateUserProfileInput | None = None
    preferences: UpdateUserPreferencesInput | None = None


class SavedLocationCreateRequest(BaseModel):
    label: LocationLabelLiteral = "home"
    display_name: str = Field(min_length=2, max_length=160)
    city: str = Field(min_length=2, max_length=120)
    state_region: str | None = Field(default=None, max_length=120)
    country_code: str = Field(default="IN", min_length=2, max_length=2)
    postal_code: str | None = Field(default=None, max_length=32)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    location_precision: LocationPrecisionLiteral = "city"
    timezone: str = Field(default="Asia/Kolkata", min_length=2, max_length=64)
    is_primary: bool = False

    @field_validator("country_code")
    @classmethod
    def uppercase_country_code(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_coordinate_precision_rules(self) -> Self:
        has_lat = self.latitude is not None
        has_lon = self.longitude is not None
        if has_lat != has_lon:
            raise ValueError("Both latitude and longitude must be provided together.")
        if self.location_precision == "exact" and not (has_lat and has_lon):
            raise ValueError("Exact location precision requires consented latitude and longitude.")
        if self.location_precision == "city":
            # Data minimization: never store exact GPS coordinates when precision is city-only
            self.latitude = None
            self.longitude = None
        return self


class SavedLocationUpdateRequest(BaseModel):
    label: LocationLabelLiteral | None = None
    display_name: str | None = Field(default=None, min_length=2, max_length=160)
    city: str | None = Field(default=None, min_length=2, max_length=120)
    state_region: str | None = Field(default=None, max_length=120)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    postal_code: str | None = Field(default=None, max_length=32)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    location_precision: LocationPrecisionLiteral | None = None
    timezone: str | None = Field(default=None, min_length=2, max_length=64)
    is_primary: bool | None = None

    @field_validator("country_code")
    @classmethod
    def uppercase_optional_country_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None

    @model_validator(mode="after")
    def validate_coordinate_pair(self) -> Self:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Both latitude and longitude must be provided together.")
        return self


class SavedLocationData(BaseModel):
    id: UUID
    label: LocationLabelLiteral
    display_name: str
    city: str
    state_region: str | None
    country_code: str
    postal_code: str | None
    latitude: float | None
    longitude: float | None
    location_precision: LocationPrecisionLiteral
    timezone: str
    is_primary: bool
    created_at: datetime


class GazetteerLocationMatch(BaseModel):
    city: str
    state_region: str
    country_code: str
    postal_prefix: str
    timezone: str


class AccountExportData(BaseModel):
    exported_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    schema_version: str = "1.0"
    account: UserMeData
    saved_locations: list[SavedLocationData]
    active_sessions_count: int
    chat_history: list[dict[str, object]] = Field(default_factory=list)
    daily_routines: list[dict[str, object]] = Field(default_factory=list)
    recommendations: list[dict[str, object]] = Field(default_factory=list)
    logged_actions: list[dict[str, object]] = Field(default_factory=list)
    alert_rules: list[dict[str, object]] = Field(default_factory=list)
    notifications: list[dict[str, object]] = Field(default_factory=list)
    community_memberships: list[dict[str, object]] = Field(default_factory=list)
