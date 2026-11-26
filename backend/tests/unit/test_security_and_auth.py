from __future__ import annotations

from app.core.security import (
    hash_ip_address,
    hash_password,
    hash_token,
    is_trusted_origin,
    verify_csrf_double_submit,
    verify_password,
)


def test_argon2id_password_hashing_and_verification() -> None:
    hashed = hash_password("SmogSafe2026!")
    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "SmogSafe2026!") is True
    assert verify_password(hashed, "WrongPassword2026!") is False
    assert verify_password(None, "SmogSafe2026!") is False
    assert verify_password("malformed-hash", "SmogSafe2026!") is False


def test_csrf_double_submit_and_origin_validation() -> None:
    assert verify_csrf_double_submit("tok-123", "tok-123") is True
    assert verify_csrf_double_submit("tok-123", "tok-456") is False
    assert verify_csrf_double_submit(None, "tok-123") is False

    allowed = {"http://localhost:3000", "https://airwise.vercel.app"}
    assert is_trusted_origin("https://airwise.vercel.app", None, allowed) is True
    assert is_trusted_origin(None, "http://localhost:3000/dashboard/settings", allowed) is True
    assert is_trusted_origin("https://evil.example.com", None, allowed) is False


def test_hmac_token_and_ip_pseudonymization() -> None:
    secret = "unit-test-secret-key-with-sufficient-length"
    digest_a = hash_token("raw-session-token", secret)
    digest_b = hash_token("raw-session-token", secret)
    assert digest_a == digest_b
    assert digest_a != "raw-session-token"
    assert hash_ip_address("203.0.113.10", secret) is not None
    assert hash_ip_address(None, secret) is None
