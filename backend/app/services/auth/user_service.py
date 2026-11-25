from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ResourceNotFoundError
from app.core.security import hash_ip_address
from app.models.identity import SavedLocation, User, UserPreference, UserProfile
from app.repositories.identity_repository import IdentityRepository
from app.schemas.identity import (
    AccountExportData,
    AgeCategoryLiteral,
    AQIStandardLiteral,
    BudgetTierLiteral,
    CommuteModeLiteral,
    LocationLabelLiteral,
    LocationPrecisionLiteral,
    SavedLocationData,
    TimeWindowSchedule,
    UpdateUserMeRequest,
    UserMeData,
    UserPreferencesData,
    UserProfileData,
)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def serialize_saved_location(record: SavedLocation) -> SavedLocationData:
    return SavedLocationData(
        id=record.id,
        label=cast(LocationLabelLiteral, record.label),
        display_name=record.display_name,
        city=record.city,
        state_region=record.state_region,
        country_code=record.country_code,
        postal_code=record.postal_code,
        latitude=record.latitude,
        longitude=record.longitude,
        location_precision=cast(LocationPrecisionLiteral, record.location_precision),
        timezone=record.timezone,
        is_primary=record.is_primary,
        created_at=_ensure_utc(record.created_at),
    )


def _serialize_user_me(user: User) -> UserMeData:
    now = datetime.now(tz=UTC)
    profile: UserProfile | None = user.profile
    prefs: UserPreference | None = user.preferences

    std: AQIStandardLiteral = (
        "us_epa"
        if profile is not None and profile.preferred_aqi_standard == "us_epa"
        else "india_naqi"
    )
    profile_data = UserProfileData(
        display_name=profile.display_name if profile is not None else user.email.split("@")[0],
        locale=profile.locale if profile is not None else "en",
        preferred_aqi_standard=std,
        timezone=profile.timezone if profile is not None else "Asia/Kolkata",
        updated_at=_ensure_utc(profile.updated_at) if profile is not None else now,
    )

    work_sched = (
        TimeWindowSchedule.model_validate(prefs.work_schedule)
        if prefs is not None and prefs.work_schedule
        else None
    )
    school_sched = (
        TimeWindowSchedule.model_validate(prefs.school_schedule)
        if prefs is not None and prefs.school_schedule
        else None
    )

    prefs_data = UserPreferencesData(
        age_category=(
            cast(AgeCategoryLiteral, prefs.age_category)
            if prefs is not None and prefs.age_category
            else None
        ),
        household_size=prefs.household_size if prefs is not None else None,
        has_vulnerable_members=prefs.has_vulnerable_members if prefs is not None else None,
        work_schedule=work_sched,
        school_schedule=school_sched,
        commute_modes=(
            [cast(CommuteModeLiteral, m) for m in prefs.commute_modes]
            if prefs is not None
            else []
        ),
        cooking_type=prefs.cooking_type if prefs is not None else None,
        ventilation_type=prefs.ventilation_type if prefs is not None else None,
        has_hepa_purifier=prefs.has_hepa_purifier if prefs is not None else False,
        budget_tier=(
            cast(BudgetTierLiteral, prefs.budget_tier)
            if prefs is not None and prefs.budget_tier
            else None
        ),
        sustainability_goals=list(prefs.sustainability_goals) if prefs is not None else [],
        save_chat_history=prefs.save_chat_history if prefs is not None else True,
        consent_updated_at=(
            _ensure_utc(prefs.consent_updated_at)
            if prefs is not None and prefs.consent_updated_at is not None
            else None
        ),
    )

    return UserMeData(
        id=user.id,
        email=user.email,
        role=user.role,
        is_email_verified=user.is_email_verified,
        created_at=_ensure_utc(user.created_at),
        profile=profile_data,
        preferences=prefs_data,
    )


class UserAccountService:
    """Service managing user profile, consented household preferences, export, and erasure."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._repo = IdentityRepository(session)
        self._settings = settings

    async def get_me(self, *, user_id: uuid.UUID) -> UserMeData:
        user = await self._repo.get_user_by_id(user_id)
        if user is None:
            raise ResourceNotFoundError("User account was not found.")
        return _serialize_user_me(user)

    async def update_me(
        self,
        *,
        user_id: uuid.UUID,
        payload: UpdateUserMeRequest,
        client_ip: str | None,
    ) -> UserMeData:
        user = await self._repo.get_user_by_id(user_id)
        if user is None:
            raise ResourceNotFoundError("User account was not found.")

        now = datetime.now(tz=UTC)
        changed_sections: list[str] = []

        if payload.profile is not None:
            if user.profile is None:
                user.profile = UserProfile(
                    user_id=user.id,
                    display_name=user.email.split("@")[0],
                    locale="en",
                    preferred_aqi_standard="india_naqi",
                    timezone="Asia/Kolkata",
                    updated_at=now,
                )
                self._session.add(user.profile)

            profile_fields = payload.profile.model_dump(exclude_unset=True)
            for field_name, field_value in profile_fields.items():
                if field_value is not None:
                    if field_name == "display_name" and isinstance(field_value, str):
                        field_value = field_value.strip()
                    setattr(user.profile, field_name, field_value)
            user.profile.updated_at = now
            changed_sections.append("profile")

        if payload.preferences is not None:
            if user.preferences is None:
                user.preferences = UserPreference(
                    user_id=user.id,
                    commute_modes=[],
                    has_hepa_purifier=False,
                    sustainability_goals=[],
                    save_chat_history=True,
                )
                self._session.add(user.preferences)

            pref_fields = payload.preferences.model_dump(exclude_unset=True)
            for field_name, field_value in pref_fields.items():
                if field_name in {"commute_modes", "sustainability_goals"} and field_value is None:
                    continue
                if field_name in {"has_hepa_purifier", "save_chat_history"} and field_value is None:
                    continue
                setattr(user.preferences, field_name, field_value)
            user.preferences.consent_updated_at = now
            changed_sections.append("preferences")

        user.updated_at = now
        await self._repo.append_audit_log(
            actor_user_id=user.id,
            action="user.updated",
            target_type="user",
            target_id=str(user.id),
            metadata_redacted={"updated_sections": changed_sections},
            ip_hash=hash_ip_address(client_ip, self._settings.auth_secret_key),
        )
        await self._session.commit()
        return _serialize_user_me(user)

    async def export_my_data(
        self, *, user_id: uuid.UUID, client_ip: str | None
    ) -> AccountExportData:
        user = await self._repo.get_user_by_id(user_id)
        if user is None:
            raise ResourceNotFoundError("User account was not found.")
        locations = await self._repo.list_saved_locations(user_id=user_id)
        active_sessions = await self._repo.list_active_sessions_for_user(user_id)

        await self._repo.append_audit_log(
            actor_user_id=user.id,
            action="user.data_exported",
            target_type="user",
            target_id=str(user.id),
            metadata_redacted={"locations_count": len(locations)},
            ip_hash=hash_ip_address(client_ip, self._settings.auth_secret_key),
        )
        await self._session.commit()

        return AccountExportData(
            account=_serialize_user_me(user),
            saved_locations=[serialize_saved_location(loc) for loc in locations],
            active_sessions_count=len(active_sessions),
        )

    async def delete_my_account(self, *, user_id: uuid.UUID, client_ip: str | None) -> None:
        user = await self._repo.get_user_by_id(user_id)
        if user is None:
            raise ResourceNotFoundError("User account was not found.")
        await self._repo.erase_user_account(
            user_id=user_id,
            ip_hash=hash_ip_address(client_ip, self._settings.auth_secret_key),
        )
        await self._session.commit()
