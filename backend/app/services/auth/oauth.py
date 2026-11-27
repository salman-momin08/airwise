"""Provider-neutral OAuth 2.0 identity adapter contracts and Google OAuth integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

from app.core.config import Settings
from app.core.exceptions import AirWiseError


@dataclass(frozen=True)
class OAuthVerifiedIdentity:
    """Normalized identity claims returned after external OAuth code verification."""

    provider: str
    provider_subject: str
    email: str
    is_email_verified: bool
    display_name: str


class OAuthIdentityAdapter(Protocol):
    """Provider-independent OAuth 2.0 identity adapter contract."""

    def is_configured(self) -> bool:
        """Return True when OAuth client credentials are present."""
        ...

    def build_authorization_url(self, state_token: str) -> str:
        """Construct an RFC-compliant authorization redirect URL."""
        ...

    async def exchange_code(self, code: str) -> OAuthVerifiedIdentity:
        """Exchange an authorization code for verified identity claims."""
        ...


class GoogleOAuthAdapterStub:
    """Typed Google OAuth 2.0 adapter stub ready for credentials."""

    def __init__(self, settings: Settings) -> None:
        self._client_id = settings.google_oauth_client_id
        self._client_secret = settings.google_oauth_client_secret
        self._redirect_uri = settings.google_oauth_redirect_uri

    def is_configured(self) -> bool:
        """Return True when both Google OAuth client ID and secret are configured."""
        return bool(self._client_id and self._client_secret)

    def build_authorization_url(self, state_token: str) -> str:
        """Build a URL-encoded Google OAuth 2.0 authorization redirect URL."""
        if not self.is_configured():
            raise AirWiseError(
                code="OAUTH_PROVIDER_NOT_CONFIGURED",
                message=(
                    "Google OAuth is not configured on this instance. "
                    "Please sign in with email and password."
                ),
                status_code=503,
            )
        query = urlencode(
            {
                "client_id": self._client_id,
                "redirect_uri": self._redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state_token,
            }
        )
        return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"

    async def exchange_code(self, _code: str) -> OAuthVerifiedIdentity:
        """Reject code exchange until live Google OAuth credentials are provisioned."""
        raise AirWiseError(
            code="OAUTH_PROVIDER_NOT_CONFIGURED",
            message="Google OAuth token exchange requires configured Google client credentials.",
            status_code=503,
        )
