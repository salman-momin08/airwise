from __future__ import annotations

class AirWiseError(Exception):
    """Base domain exception mapped centrally to the /api/v1 error envelope."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code

class AuthenticationError(AirWiseError):
    def __init__(
        self,
        message: str = "Authentication required.",
        code: str = "AUTH_REQUIRED",
    ) -> None:
        super().__init__(code=code, message=message, status_code=401)

class AuthorizationError(AirWiseError):
    def __init__(
        self,
        message: str = "You do not have permission to access this resource.",
        code: str = "AUTH_FORBIDDEN",
    ) -> None:
        super().__init__(code=code, message=message, status_code=403)

class ConflictError(AirWiseError):
    def __init__(self, message: str = "Resource conflict.") -> None:
        super().__init__(code="CONFLICT", message=message, status_code=409)

class RateLimitExceededError(AirWiseError):
    def __init__(
        self,
        message: str = "Too many requests. Please wait before trying again.",
        code: str = "RATE_LIMIT_EXCEEDED",
    ) -> None:
        super().__init__(code=code, message=message, status_code=429)

class ResourceNotFoundError(AirWiseError):
    def __init__(self, message: str = "Requested resource was not found.") -> None:
        super().__init__(code="RESOURCE_NOT_FOUND", message=message, status_code=404)

class ExternalProviderUnavailableError(AirWiseError):
    def __init__(
        self,
        code: str = "AIR_QUALITY_PROVIDER_UNAVAILABLE",
        message: str = "Current environmental data is temporarily unavailable.",
    ) -> None:
        super().__init__(code=code, message=message, status_code=503)
