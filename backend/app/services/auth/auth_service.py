"""Session issuance, rotation, reuse detection, password reset, and email verification service."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import (
    AirWiseError,
    AuthenticationError,
    ConflictError,
    ResourceNotFoundError,
)
from app.core.security import (
    UserRole,
    generate_secure_token,
    hash_ip_address,
    hash_password,
    hash_token,
    password_needs_rehash,
    verify_password,
)
from app.integrations.email.provider import EmailProvider, TransactionalEmailMessage
from app.models.identity import User, UserSession
from app.repositories.identity_repository import IdentityRepository
from app.schemas.identity import (
    AQIStandardLiteral,
    AuthPrincipalData,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SessionItem,
)

EMAIL_VERIFICATION_TTL_HOURS = 24
PASSWORD_RESET_TTL_MINUTES = 30
SESSION_RETENTION_DAYS = 30


@dataclass(frozen=True)
class IssuedSessionBundle:
    principal: AuthPrincipalData
    raw_session_token: str
    raw_csrf_token: str
    max_age_seconds: int


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _to_principal_data(user: User, session_id: uuid.UUID) -> AuthPrincipalData:
    preferred_std = (
        user.profile.preferred_aqi_standard if user.profile is not None else "india_naqi"
    )
    standard: AQIStandardLiteral = "us_epa" if preferred_std == "us_epa" else "india_naqi"
    return AuthPrincipalData(
        user_id=str(user.id),
        email=user.email,
        display_name=user.profile.display_name if user.profile is not None else None,
        role=user.role,
        is_email_verified=user.is_email_verified,
        preferred_aqi_standard=standard,
        session_id=str(session_id),
    )


class AuthService:
    """Domain service for registration, login, session rotation, revocation, and resets."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        email_provider: EmailProvider,
    ) -> None:
        self._session = session
        self._repo = IdentityRepository(session)
        self._settings = settings
        self._email_provider = email_provider

    async def _issue_session_bundle(
        self,
        *,
        user: User,
        client_ip: str | None,
        user_agent: str | None,
    ) -> tuple[UserSession, IssuedSessionBundle]:
        raw_session_token = generate_secure_token(32)
        raw_csrf_token = generate_secure_token(24)
        ttl_seconds = self._settings.auth_session_ttl_seconds
        expires_at = datetime.now(tz=UTC) + timedelta(seconds=ttl_seconds)

        session_record = await self._repo.create_session(
            user_id=user.id,
            refresh_token_hash=hash_token(raw_session_token, self._settings.auth_secret_key),
            csrf_secret_hash=hash_token(raw_csrf_token, self._settings.auth_secret_key),
            ip_hash=hash_ip_address(client_ip, self._settings.auth_secret_key),
            user_agent=user_agent,
            expires_at=expires_at,
        )
        bundle = IssuedSessionBundle(
            principal=_to_principal_data(user, session_record.id),
            raw_session_token=raw_session_token,
            raw_csrf_token=raw_csrf_token,
            max_age_seconds=ttl_seconds,
        )
        return session_record, bundle

    async def register_user(
        self,
        payload: RegisterRequest,
        *,
        client_ip: str | None,
        user_agent: str | None,
    ) -> IssuedSessionBundle:
        existing = await self._repo.get_user_by_email(payload.email)
        if existing is not None:
            raise ConflictError("An account with this email address already exists.")

        user = await self._repo.create_user_with_defaults(
            email=payload.email,
            password_hash=hash_password(payload.password),
            display_name=payload.display_name,
            preferred_aqi_standard=payload.preferred_aqi_standard,
            timezone=payload.timezone,
            locale=payload.locale,
            role=UserRole.USER.value,
        )

        raw_verify_token = generate_secure_token(32)
        await self._repo.create_action_token(
            user_id=user.id,
            purpose="email_verification",
            token_hash=hash_token(raw_verify_token, self._settings.auth_secret_key),
            expires_at=datetime.now(tz=UTC) + timedelta(hours=EMAIL_VERIFICATION_TTL_HOURS),
        )

        _session_record, bundle = await self._issue_session_bundle(
            user=user,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        await self._repo.append_audit_log(
            actor_user_id=user.id,
            action="auth.register",
            target_type="user",
            target_id=str(user.id),
            metadata_redacted={"preferred_aqi_standard": payload.preferred_aqi_standard},
            ip_hash=hash_ip_address(client_ip, self._settings.auth_secret_key),
        )
        await self._session.commit()

        verify_link = f"{self._settings.frontend_url}/login?verify_token={raw_verify_token}"
        await self._email_provider.send_email(
            TransactionalEmailMessage(
                to_email=user.email,
                subject="Verify your AirWise AI email address",
                text_body=(
                    f"Welcome to AirWise AI, {payload.display_name}.\n\n"
                    f"Verify your email within 24 hours: {verify_link}\n"
                ),
            )
        )
        return bundle

    async def login_user(
        self,
        payload: LoginRequest,
        *,
        client_ip: str | None,
        user_agent: str | None,
    ) -> IssuedSessionBundle:
        user = await self._repo.get_user_by_email(payload.email)
        if user is None or not user.is_active:
            # Dummy verification mitigates timing side-channel enumeration
            verify_password(
                "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQxMjM0NTY3OA$RdescudvJCsgt3ub+b+dWRWJTmaaJObG",
                payload.password,
            )
            raise AuthenticationError(
                message="Invalid email or password.",
                code="AUTH_INVALID_CREDENTIALS",
            )

        if not verify_password(user.password_hash, payload.password):
            raise AuthenticationError(
                message="Invalid email or password.",
                code="AUTH_INVALID_CREDENTIALS",
            )

        if user.password_hash and password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(payload.password)

        _session_record, bundle = await self._issue_session_bundle(
            user=user,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        await self._repo.append_audit_log(
            actor_user_id=user.id,
            action="auth.login",
            target_type="user_session",
            target_id=bundle.principal.session_id,
            metadata_redacted={},
            ip_hash=hash_ip_address(client_ip, self._settings.auth_secret_key),
        )
        await self._session.commit()
        return bundle

    async def resolve_session_cookie(
        self, raw_session_token: str | None
    ) -> AuthPrincipalData | None:
        if not raw_session_token:
            return None
        token_digest = hash_token(raw_session_token, self._settings.auth_secret_key)
        found = await self._repo.get_session_by_token_hash(token_digest)
        if found is None:
            return None
        session_record, user = found
        now = datetime.now(tz=UTC)
        if session_record.revoked_at is not None or _ensure_utc(session_record.expires_at) <= now:
            return None
        return _to_principal_data(user, session_record.id)

    async def rotate_session(
        self,
        *,
        raw_session_token: str | None,
        client_ip: str | None,
        user_agent: str | None,
    ) -> IssuedSessionBundle:
        if not raw_session_token:
            raise AuthenticationError(
                message="Session has expired. Please sign in again.",
                code="AUTH_SESSION_EXPIRED",
            )
        token_digest = hash_token(raw_session_token, self._settings.auth_secret_key)
        found = await self._repo.get_session_by_token_hash(token_digest)
        if found is None:
            raise AuthenticationError(
                message="Session has expired. Please sign in again.",
                code="AUTH_SESSION_EXPIRED",
            )
        session_record, user = found
        now = datetime.now(tz=UTC)

        if session_record.revoked_at is not None:
            # Reuse detection: revoke all remaining active sessions for this user
            await self._repo.revoke_all_sessions_for_user(user_id=user.id)
            await self._repo.append_audit_log(
                actor_user_id=user.id,
                action="auth.session_reuse_detected",
                target_type="user",
                target_id=str(user.id),
                metadata_redacted={"revoked_session_id": str(session_record.id)},
                ip_hash=hash_ip_address(client_ip, self._settings.auth_secret_key),
            )
            await self._session.commit()
            raise AuthenticationError(
                message=(
                    "Session token was already rotated or revoked. "
                    "All active sessions have been invalidated for your protection."
                ),
                code="AUTH_SESSION_EXPIRED",
            )

        if _ensure_utc(session_record.expires_at) <= now:
            session_record.revoked_at = now
            await self._session.commit()
            raise AuthenticationError(
                message="Session has expired. Please sign in again.",
                code="AUTH_SESSION_EXPIRED",
            )

        session_record.revoked_at = now
        _new_record, bundle = await self._issue_session_bundle(
            user=user,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        await self._session.commit()
        return bundle

    async def logout_current_session(
        self, *, user_id: uuid.UUID, session_id: uuid.UUID | None, client_ip: str | None
    ) -> None:
        if session_id is not None:
            await self._repo.revoke_session_for_user(user_id=user_id, session_id=session_id)
        await self._repo.append_audit_log(
            actor_user_id=user_id,
            action="auth.logout",
            target_type="user_session",
            target_id=str(session_id) if session_id else None,
            metadata_redacted={},
            ip_hash=hash_ip_address(client_ip, self._settings.auth_secret_key),
        )
        await self._session.commit()

    async def list_sessions(
        self, *, user_id: uuid.UUID, current_session_id: uuid.UUID | None
    ) -> list[SessionItem]:
        rows = await self._repo.list_active_sessions_for_user(user_id)
        return [
            SessionItem(
                id=row.id,
                user_agent=row.user_agent,
                created_at=_ensure_utc(row.created_at),
                expires_at=_ensure_utc(row.expires_at),
                is_current=(current_session_id is not None and row.id == current_session_id),
            )
            for row in rows
        ]

    async def revoke_specific_session(
        self, *, user_id: uuid.UUID, target_session_id: uuid.UUID, client_ip: str | None
    ) -> None:
        revoked = await self._repo.revoke_session_for_user(
            user_id=user_id, session_id=target_session_id
        )
        if not revoked:
            raise ResourceNotFoundError("Active session not found.")
        await self._repo.append_audit_log(
            actor_user_id=user_id,
            action="auth.session_revoked",
            target_type="user_session",
            target_id=str(target_session_id),
            metadata_redacted={},
            ip_hash=hash_ip_address(client_ip, self._settings.auth_secret_key),
        )
        await self._session.commit()

    async def revoke_other_sessions(
        self, *, user_id: uuid.UUID, current_session_id: uuid.UUID | None, client_ip: str | None
    ) -> int:
        count = await self._repo.revoke_all_sessions_for_user(
            user_id=user_id, except_session_id=current_session_id
        )
        await self._repo.append_audit_log(
            actor_user_id=user_id,
            action="auth.revoke_other_sessions",
            target_type="user",
            target_id=str(user_id),
            metadata_redacted={"revoked_count": count},
            ip_hash=hash_ip_address(client_ip, self._settings.auth_secret_key),
        )
        await self._session.commit()
        return count

    async def request_password_reset(self, email: str, *, client_ip: str | None) -> None:
        user = await self._repo.get_user_by_email(email)
        if user is None or not user.is_active:
            # Always succeed silently to prevent account enumeration
            return
        raw_reset_token = generate_secure_token(32)
        await self._repo.create_action_token(
            user_id=user.id,
            purpose="password_reset",
            token_hash=hash_token(raw_reset_token, self._settings.auth_secret_key),
            expires_at=datetime.now(tz=UTC) + timedelta(minutes=PASSWORD_RESET_TTL_MINUTES),
        )
        await self._repo.append_audit_log(
            actor_user_id=user.id,
            action="auth.password_reset_requested",
            target_type="user",
            target_id=str(user.id),
            metadata_redacted={},
            ip_hash=hash_ip_address(client_ip, self._settings.auth_secret_key),
        )
        await self._session.commit()

        reset_link = f"{self._settings.frontend_url}/forgot-password?token={raw_reset_token}"
        await self._email_provider.send_email(
            TransactionalEmailMessage(
                to_email=user.email,
                subject="Reset your AirWise AI password",
                text_body=(
                    "A password reset was requested for your AirWise AI account.\n\n"
                    f"Use this single-use link within {PASSWORD_RESET_TTL_MINUTES} minutes:\n"
                    f"{reset_link}\n\n"
                    "If you did not request this, you can safely ignore this email."
                ),
            )
        )

    async def reset_password(self, payload: ResetPasswordRequest, *, client_ip: str | None) -> None:
        token_digest = hash_token(payload.token, self._settings.auth_secret_key)
        token_record = await self._repo.get_valid_action_token(
            purpose="password_reset",
            token_hash=token_digest,
        )
        if token_record is None:
            raise AirWiseError(
                code="INVALID_RESET_TOKEN",
                message="This password reset link is invalid or has expired.",
                status_code=400,
            )
        user = await self._repo.get_user_by_id(token_record.user_id)
        if user is None or not user.is_active:
            raise AirWiseError(
                code="INVALID_RESET_TOKEN",
                message="This password reset link is invalid or has expired.",
                status_code=400,
            )

        now = datetime.now(tz=UTC)
        token_record.used_at = now
        user.password_hash = hash_password(payload.new_password)
        user.updated_at = now
        revoked_count = await self._repo.revoke_all_sessions_for_user(user_id=user.id)
        await self._repo.append_audit_log(
            actor_user_id=user.id,
            action="auth.password_reset_completed",
            target_type="user",
            target_id=str(user.id),
            metadata_redacted={"revoked_sessions": revoked_count},
            ip_hash=hash_ip_address(client_ip, self._settings.auth_secret_key),
        )
        await self._session.commit()

    async def verify_email(self, raw_token: str, *, client_ip: str | None) -> None:
        token_digest = hash_token(raw_token, self._settings.auth_secret_key)
        token_record = await self._repo.get_valid_action_token(
            purpose="email_verification",
            token_hash=token_digest,
        )
        if token_record is None:
            raise AirWiseError(
                code="INVALID_VERIFICATION_TOKEN",
                message="This email verification link is invalid or has expired.",
                status_code=400,
            )
        user = await self._repo.get_user_by_id(token_record.user_id)
        if user is None:
            raise ResourceNotFoundError("User account not found.")

        now = datetime.now(tz=UTC)
        token_record.used_at = now
        user.is_email_verified = True
        user.updated_at = now
        await self._repo.append_audit_log(
            actor_user_id=user.id,
            action="auth.email_verified",
            target_type="user",
            target_id=str(user.id),
            metadata_redacted={},
            ip_hash=hash_ip_address(client_ip, self._settings.auth_secret_key),
        )
        await self._session.commit()

    async def cleanup_expired_sessions(self) -> int:
        cutoff = datetime.now(tz=UTC) - timedelta(days=SESSION_RETENTION_DAYS)
        purged = await self._repo.purge_expired_sessions(retention_cutoff=cutoff)
        await self._session.commit()
        return purged
