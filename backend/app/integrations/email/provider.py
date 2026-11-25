from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx
import structlog

from app.core.config import get_settings
from app.core.exceptions import ExternalProviderUnavailableError

logger = structlog.get_logger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


@dataclass(frozen=True)
class TransactionalEmailMessage:
    to_email: str
    subject: str
    text_body: str


class EmailProvider(Protocol):
    async def send_email(self, message: TransactionalEmailMessage) -> str: ...


class ConsoleEmailProvider:
    """Development & test email sink that records redacted delivery metadata without leaking PII."""

    last_outbox: list[TransactionalEmailMessage] = []

    async def send_email(self, message: TransactionalEmailMessage) -> str:
        if get_settings().app_env in {"development", "test"}:
            self.last_outbox.append(message)
            if len(self.last_outbox) > 50:
                self.last_outbox.pop(0)
        logger.info("transactional_email_dispatched_console", subject=message.subject)
        return "console-delivery"


class ResendEmailProvider:
    """Zero-cost friendly transactional email adapter via Resend HTTPS API."""

    def __init__(self, api_key: str, from_address: str) -> None:
        self._api_key = api_key
        self._from_address = from_address

    async def send_email(self, message: TransactionalEmailMessage) -> str:
        if not self._api_key:
            raise ExternalProviderUnavailableError(
                code="EMAIL_PROVIDER_UNAVAILABLE",
                message="Transactional email delivery is temporarily unavailable.",
            )
        timeout = httpx.Timeout(connect=3.0, read=8.0, write=5.0, pool=3.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            try:
                response = await client.post(
                    RESEND_API_URL,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "from": self._from_address,
                        "to": [message.to_email],
                        "subject": message.subject,
                        "text": message.text_body,
                    },
                )
                response.raise_for_status()
                body = response.json()
                return str(body.get("id", "resend-accepted"))
            except httpx.HTTPError as exc:
                logger.error("resend_email_failed", status=getattr(exc, "response", None))
                raise ExternalProviderUnavailableError(
                    code="EMAIL_PROVIDER_UNAVAILABLE",
                    message="Transactional email delivery is temporarily unavailable.",
                ) from exc


def get_email_provider() -> EmailProvider:
    settings = get_settings()
    if settings.email_provider == "resend":
        return ResendEmailProvider(
            api_key=settings.email_api_key,
            from_address=settings.email_from_address,
        )
    return ConsoleEmailProvider()
