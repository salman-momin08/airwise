from __future__ import annotations

import hashlib
import hmac
import secrets
from enum import StrEnum


class UserRole(StrEnum):
    GUEST = "guest"
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


def generate_secure_token(nbytes: int = 32) -> str:
    """Generate a URL-safe cryptographically random token."""
    return secrets.token_urlsafe(nbytes)


def hash_token(raw_token: str, secret_key: str) -> str:
    """Create an HMAC-SHA256 digest for storing session or CSRF tokens safely."""
    return hmac.new(
        key=secret_key.encode("utf-8"),
        msg=raw_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def verify_csrf_double_submit(cookie_token: str | None, header_token: str | None) -> bool:
    """Constant-time verification of double-submit CSRF cookie and header tokens."""
    if not cookie_token or not header_token:
        return False
    return hmac.compare_digest(cookie_token, header_token)
