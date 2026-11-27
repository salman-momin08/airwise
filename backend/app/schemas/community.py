"""Pydantic v2 DTOs for neighborhood communities, initiatives, participation, and moderation."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ChallengeTypeLiteral = Literal[
    "no_idling_school_week",
    "public_transit_challenge",
    "carpool_corridor",
    "clean_cooking_awareness",
    "indoor_clean_air_drive",
]
ModerationStatusLiteral = Literal["pending_review", "active", "hidden", "archived"]
ReportReasonLiteral = Literal[
    "pii_exposure",
    "misinformation",
    "unsafe_health_advice",
    "harassment_or_spam",
]
ReportResolutionStatusLiteral = Literal["open", "resolved_removed", "dismissed"]

_DISALLOWED_COMMUNITY_PII = re.compile(
    r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}"
    r"|(?<!\w)[+-]?\d{1,3}\.\d{3,}\s*[, /]\s*[+-]?\d{1,3}\.\d{3,}"
    r"|\b(?:\+?\d[\d ()-]{8,}\d)\b"
    r"|\b(?:house|flat|apt|apartment|plot|door)\s*(?:no\.?|number|#)?\s*\d+[a-zA-Z]?\b",
    re.IGNORECASE,
)


def _reject_pii_or_exact_address(value: str) -> str:
    if _DISALLOWED_COMMUNITY_PII.search(value):
        raise ValueError(
            "Community fields must remain coarse and privacy-preserving: never include "
            "household unit numbers, street addresses, exact GPS coordinates, emails, or phones."
        )
    return value


class CreateCommunityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    slug: str = Field(min_length=3, max_length=96, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=3, max_length=160)
    city: str = Field(min_length=2, max_length=120, pattern=r"^[\w .'-]+$")
    coarse_boundary_label: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=10, max_length=1200)
    moderation_policy: str = Field(
        default=(
            "Coarse neighborhood boundaries only; no street addresses, exact coordinates, "
            "unconsented personal names, or unsupported medical/AQI claims."
        ),
        min_length=10,
        max_length=800,
    )

    @field_validator("name", "coarse_boundary_label", "description")
    @classmethod
    def check_no_pii(cls, value: str) -> str:
        return _reject_pii_or_exact_address(value)


class JoinCommunityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public_display_consent: bool = False


class CommunitySummarySchema(BaseModel):
    id: UUID
    slug: str
    name: str
    city: str
    coarse_boundary_label: str
    description: str
    member_count: int
    active_initiatives_count: int
    is_current_user_member: bool = False
    current_user_public_display_consent: bool = False
    created_at: datetime


class CommunityDetailSchema(CommunitySummarySchema):
    moderation_policy: str
    total_self_reported_actions: int
    total_estimated_avoided_co2e_kg: float
    consented_member_display_names: list[str] = Field(default_factory=list)
    privacy_and_methodology_notice: str = (
        "Privacy-preserving aggregate metrics: exact household locations are never collected "
        "or displayed, member names appear only with explicit opt-in consent, and voluntary "
        "action totals are deterministic CO2e estimates—not measured ambient AQI reductions."
    )


class CreateInitiativeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=4, max_length=200)
    description: str = Field(min_length=10, max_length=1200)
    challenge_type: ChallengeTypeLiteral
    starts_at: datetime
    ends_at: datetime

    @field_validator("title", "description")
    @classmethod
    def check_no_pii(cls, value: str) -> str:
        return _reject_pii_or_exact_address(value)

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at.")
        return self


class CommunityInitiativeSchema(BaseModel):
    id: UUID
    community_id: UUID
    community_name: str | None = None
    city: str | None = None
    title: str
    description: str
    challenge_type: ChallengeTypeLiteral
    starts_at: datetime
    ends_at: datetime
    moderation_status: ModerationStatusLiteral
    participant_entries_count: int = 0
    total_self_reported_actions: int = 0
    total_estimated_avoided_co2e_kg: float = 0.0
    is_self_reported_aggregate: Literal[True] = True
    created_at: datetime


class LogParticipationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    self_reported_actions_count: int = Field(ge=1, le=50)
    commute_distance_saved_km: float = Field(default=0.0, ge=0.0, le=500.0)
    note: str | None = Field(default=None, max_length=280)

    @field_validator("note")
    @classmethod
    def check_note_no_pii(cls, value: str | None) -> str | None:
        return _reject_pii_or_exact_address(value) if value is not None else None


class ParticipationReceiptSchema(BaseModel):
    id: UUID
    initiative_id: UUID
    self_reported_actions_count: int
    estimated_avoided_co2e_kg: float
    is_self_reported: Literal[True] = True
    is_estimate: Literal[True] = True
    reported_at: datetime


class CreateAbuseReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    initiative_id: UUID | None = None
    reason_category: ReportReasonLiteral
    details: str = Field(min_length=8, max_length=500)


class ResolveAbuseReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action: Literal["dismiss", "hide_initiative"]
    resolution_note: str = Field(min_length=4, max_length=400)


class ModerateInitiativeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    moderation_status: Literal["active", "hidden", "archived"]
    reason: str = Field(min_length=4, max_length=300)


class AbuseReportSchema(BaseModel):
    id: UUID
    community_id: UUID
    initiative_id: UUID | None = None
    reason_category: ReportReasonLiteral
    details: str
    status: ReportResolutionStatusLiteral
    resolution_note: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None
