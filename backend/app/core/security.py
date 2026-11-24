from __future__ import annotations

import hashlib
import hmac
import secrets
from enum import StrEnum
from urllib.parse import urlparse

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

SESSION_COOKIE_NAME = "airwise_session"
CSRF_COOKIE_NAME = "airwise_csrf"

_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


class UserRole(StrEnum):
    GUEST = "guest"
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


def hash_password(raw_password: str) -> str:
    """Hash a plaintext password using OWASP-recommended Argon2id parameters."""
    return str(_password_hasher.hash(raw_password))


def verify_password(password_hash: str | None, candidate_password: str) -> bool:
    """Constant-time Argon2id password verification."""
    if not password_hash:
        return False
    try:
        return bool(_password_hasher.verify(password_hash, candidate_password))
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    """Check whether stored Argon2id parameters should be upgraded."""
    return bool(_password_hasher.check_needs_rehash(password_hash))


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


def hash_ip_address(ip_address: str | None, secret_key: str) -> str | None:
    """Pseudonymize client IP addresses before persisting to session or audit records."""
    if not ip_address:
        return None
    return hash_token(ip_address.strip(), secret_key)


def verify_csrf_double_submit(cookie_token: str | None, header_token: str | None) -> bool:
    """Constant-time verification of double-submit CSRF cookie and header tokens."""
    if not cookie_token or not header_token:
        return False
    return hmac.compare_digest(cookie_token, header_token)


def extract_origin(url_or_origin: str | None) -> str | None:
    """Normalize an Origin or Referer header to scheme://netloc."""
    if not url_or_origin:
        return None
    parsed = urlparse(url_or_origin)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def is_trusted_origin(
    origin_header: str | None,
    referer_header: str | None,
    allowed_origins: set[str],
) -> bool:
    """Verify Origin/Referer when present on state-changing cookie requests."""
    candidate = extract_origin(origin_header) or extract_origin(referer_header)
    if candidate is None:
        return True
    normalized_allowed = {
        norm for item in allowed_origins if (norm := extract_origin(item)) is not None
    }
    return candidate in normalized_allowed
