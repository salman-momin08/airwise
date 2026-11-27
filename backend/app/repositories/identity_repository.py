from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from geoalchemy2.elements import WKTElement
from sqlalchemy import CursorResult, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.identity import (
    AuditLog,
    SavedLocation,
    SystemSetting,
    User,
    UserActionToken,
    UserPreference,
    UserProfile,
    UserSession,
)
from app.repositories.alerts_community_repository import AlertsCommunityRepository
from app.repositories.assistant_repository import AssistantRepository
from app.repositories.planning_repository import PlanningRepository

class IdentityRepository:
    """Async SQLAlchemy 2.x repository enforcing strict object-level user_id scoping."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _is_postgresql(self) -> bool:
        bind = self._session.get_bind()
        return bind.dialect.name == "postgresql"

    def _build_coordinates_value(
        self, latitude: float | None, longitude: float | None
    ) -> Any | None:
        if latitude is None or longitude is None:
            return None
        wkt = f"POINT({longitude} {latitude})"
        if self._is_postgresql():
            return WKTElement(wkt, srid=4326)
        return wkt

    async def get_user_by_email(self, email: str) -> User | None:
        normalized = email.strip().lower()
        stmt = (
            select(User)
            .options(selectinload(User.profile), selectinload(User.preferences))
            .where(func.lower(User.email) == normalized, User.deleted_at.is_(None))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = (
            select(User)
            .options(selectinload(User.profile), selectinload(User.preferences))
            .where(User.id == user_id, User.deleted_at.is_(None))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user_with_defaults(
        self,
        *,
        email: str,
        password_hash: str,
        display_name: str,
        preferred_aqi_standard: str,
        timezone: str,
        locale: str,
        role: str = "user",
    ) -> User:
        now = datetime.now(tz=UTC)
        user = User(
            id=uuid.uuid4(),
            email=email.strip().lower(),
            password_hash=password_hash,
            role=role,
            is_email_verified=False,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        profile = UserProfile(
            user_id=user.id,
            display_name=display_name,
            locale=locale,
            preferred_aqi_standard=preferred_aqi_standard,
            timezone=timezone,
            updated_at=now,
        )
        preferences = UserPreference(
            user_id=user.id,
            commute_modes=[],
            has_hepa_purifier=False,
            sustainability_goals=[],
            save_chat_history=True,
        )
        user.profile = profile
        user.preferences = preferences
        self._session.add_all([user, profile, preferences])
        await self._session.flush()
        return user

    async def create_session(
        self,
        *,
        user_id: uuid.UUID,
        refresh_token_hash: str,
        csrf_secret_hash: str,
        ip_hash: str | None,
        user_agent: str | None,
        expires_at: datetime,
    ) -> UserSession:
        record = UserSession(
            id=uuid.uuid4(),
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            csrf_secret_hash=csrf_secret_hash,
            ip_hash=ip_hash,
            user_agent=(user_agent[:512] if user_agent else None),
            expires_at=expires_at,
            created_at=datetime.now(tz=UTC),
        )
        self._session.add(record)
        return record

    async def get_session_by_token_hash(
        self, refresh_token_hash: str
    ) -> tuple[UserSession, User] | None:
        stmt = (
            select(UserSession, User)
            .join(User, User.id == UserSession.user_id)
            .options(selectinload(User.profile))
            .where(
                UserSession.refresh_token_hash == refresh_token_hash,
                User.deleted_at.is_(None),
                User.is_active.is_(True),
            )
        )
        result = await self._session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        return row[0], row[1]

    async def list_active_sessions_for_user(self, user_id: uuid.UUID) -> list[UserSession]:
        now = datetime.now(tz=UTC)
        stmt = (
            select(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
            )
            .order_by(UserSession.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def revoke_session_for_user(
        self, *, user_id: uuid.UUID, session_id: uuid.UUID
    ) -> bool:
        now = datetime.now(tz=UTC)
        stmt = (
            update(UserSession)
            .where(
                UserSession.id == session_id,
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        cursor = cast(CursorResult[Any], await self._session.execute(stmt))
        return bool(cursor.rowcount and cursor.rowcount > 0)

    async def revoke_all_sessions_for_user(
        self, *, user_id: uuid.UUID, except_session_id: uuid.UUID | None = None
    ) -> int:
        now = datetime.now(tz=UTC)
        stmt = update(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
        if except_session_id is not None:
            stmt = stmt.where(UserSession.id != except_session_id)
        cursor = cast(CursorResult[Any], await self._session.execute(stmt.values(revoked_at=now)))
        return int(cursor.rowcount or 0)

    async def purge_expired_sessions(self, *, retention_cutoff: datetime) -> int:
        now = datetime.now(tz=UTC)
        stmt = delete(UserSession).where(
            (UserSession.expires_at < retention_cutoff)
            | (
                UserSession.revoked_at.is_not(None)
                & (UserSession.revoked_at < retention_cutoff)
            )
            | ((UserSession.expires_at < now) & UserSession.revoked_at.is_not(None))
        )
        cursor = cast(CursorResult[Any], await self._session.execute(stmt))
        return int(cursor.rowcount or 0)

    async def create_action_token(
        self,
        *,
        user_id: uuid.UUID,
        purpose: str,
        token_hash: str,
        expires_at: datetime,
    ) -> UserActionToken:
        record = UserActionToken(
            id=uuid.uuid4(),
            user_id=user_id,
            purpose=purpose,
            token_hash=token_hash,
            expires_at=expires_at,
            created_at=datetime.now(tz=UTC),
        )
        self._session.add(record)
        return record

    async def get_valid_action_token(
        self, *, purpose: str, token_hash: str
    ) -> UserActionToken | None:
        now = datetime.now(tz=UTC)
        stmt = select(UserActionToken).where(
            UserActionToken.purpose == purpose,
            UserActionToken.token_hash == token_hash,
            UserActionToken.used_at.is_(None),
            UserActionToken.expires_at > now,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_saved_locations(self, *, user_id: uuid.UUID) -> list[SavedLocation]:
        stmt = (
            select(SavedLocation)
            .where(SavedLocation.user_id == user_id)
            .order_by(SavedLocation.is_primary.desc(), SavedLocation.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_saved_location_for_user(
        self, *, user_id: uuid.UUID, location_id: uuid.UUID
    ) -> SavedLocation | None:
        stmt = select(SavedLocation).where(
            SavedLocation.id == location_id,
            SavedLocation.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def clear_primary_locations_for_user(self, *, user_id: uuid.UUID) -> None:
        stmt = (
            update(SavedLocation)
            .where(SavedLocation.user_id == user_id, SavedLocation.is_primary.is_(True))
            .values(is_primary=False)
        )
        await self._session.execute(stmt)

    async def create_saved_location(
        self,
        *,
        user_id: uuid.UUID,
        label: str,
        display_name: str,
        city: str,
        state_region: str | None,
        country_code: str,
        postal_code: str | None,
        latitude: float | None,
        longitude: float | None,
        location_precision: str,
        timezone: str,
        is_primary: bool,
    ) -> SavedLocation:
        record = SavedLocation(
            id=uuid.uuid4(),
            user_id=user_id,
            label=label,
            display_name=display_name,
            city=city,
            state_region=state_region,
            country_code=country_code,
            postal_code=postal_code,
            coordinates=self._build_coordinates_value(latitude, longitude),
            latitude=latitude,
            longitude=longitude,
            location_precision=location_precision,
            timezone=timezone,
            is_primary=is_primary,
            created_at=datetime.now(tz=UTC),
        )
        self._session.add(record)
        return record

    def update_saved_location_coordinates(
        self,
        record: SavedLocation,
        *,
        latitude: float | None,
        longitude: float | None,
    ) -> None:
        record.latitude = latitude
        record.longitude = longitude
        record.coordinates = self._build_coordinates_value(latitude, longitude)

    async def delete_saved_location(self, record: SavedLocation) -> None:
        await self._session.delete(record)

    async def append_audit_log(
        self,
        *,
        actor_user_id: uuid.UUID | None,
        action: str,
        target_type: str,
        target_id: str | None,
        metadata_redacted: dict[str, Any] | None = None,
        ip_hash: str | None = None,
    ) -> AuditLog:
        log = AuditLog(
            id=uuid.uuid4(),
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_redacted=metadata_redacted or {},
            ip_hash=ip_hash,
            created_at=datetime.now(tz=UTC),
        )
        self._session.add(log)
        return log

    async def erase_user_account(self, *, user_id: uuid.UUID, ip_hash: str | None) -> None:
        """Delete personal records, revoke sessions, and anonymize audit_logs actor_user_id."""
        await AssistantRepository(self._session).delete_history(user_id=user_id)
        await PlanningRepository(self._session).erase_user_data(user_id=user_id)
        await AlertsCommunityRepository(self._session).erase_and_anonymize_user_data(
            user_id=user_id
        )
        await self._session.execute(
            update(AuditLog)
            .where(AuditLog.actor_user_id == user_id)
            .values(actor_user_id=None)
        )
        await self._session.execute(
            update(SystemSetting)
            .where(SystemSetting.updated_by == user_id)
            .values(updated_by=None)
        )
        await self._session.execute(
            delete(SavedLocation).where(SavedLocation.user_id == user_id)
        )
        await self._session.execute(
            delete(UserActionToken).where(UserActionToken.user_id == user_id)
        )
        await self._session.execute(
            delete(UserSession).where(UserSession.user_id == user_id)
        )
        await self._session.execute(
            delete(UserPreference).where(UserPreference.user_id == user_id)
        )
        await self._session.execute(
            delete(UserProfile).where(UserProfile.user_id == user_id)
        )
        await self._session.execute(delete(User).where(User.id == user_id))
        await self.append_audit_log(
            actor_user_id=None,
            action="user.account_deleted",
            target_type="user",
            target_id="anonymized",
            metadata_redacted={"erasure_completed": True},
            ip_hash=ip_hash,
        )
