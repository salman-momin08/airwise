from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings
from app.core.exceptions import AirWiseError

@dataclass(frozen=True)
class OAuthVerifiedIdentity:
    provider: str
    provider_subject: str
    email: str
    is_email_verified: bool
    display_name: str

class OAuthIdentityAdapter(Protocol):
    """Provider-independent OAuth 2.0 identity adapter contract."""

    def is_configured(self) -> bool: ...

    def build_authorization_url(self, state_token: str) -> str: ...

    async def exchange_code(self, code: str) -> OAuthVerifiedIdentity: ...

class GoogleOAuthAdapterStub:
    """Typed Google OAuth 2.0 adapter stub ready for credentials."""

    def __init__(self, settings: Settings) -> None:
        self._client_id = settings.google_oauth_client_id
        self._client_secret = settings.google_oauth_client_secret
        self._redirect_uri = settings.google_oauth_redirect_uri

    def is_configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def build_authorization_url(self, state_token: str) -> str:
        if not self.is_configured():
            raise AirWiseError(
                code="OAUTH_PROVIDER_NOT_CONFIGURED",
                message=(
                    "Google OAuth is not configured on this instance. "
                    "Please sign in with email and password."
                ),
                status_code=503,
            )
        return (
            "https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={self._client_id}"
            f"&redirect_uri={self._redirect_uri}"
            "&response_type=code&scope=openid%20email%20profile"
            f"&state={state_token}"
        )

    async def exchange_code(self, _code: str) -> OAuthVerifiedIdentity:
        raise AirWiseError(
            code="OAUTH_PROVIDER_NOT_CONFIGURED",
            message="Google OAuth token exchange requires configured Google client credentials.",
            status_code=503,
        )
