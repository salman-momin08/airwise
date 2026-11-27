"""Canonical `/api/v1/` success, error, pagination, and system health envelope schemas."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class PaginationMeta(BaseModel):
    cursor: str | None = None
    has_more: bool = False
    limit: int = 20


class ResponseMeta(BaseModel):
    request_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    pagination: PaginationMeta | None = None


class ApiResponse[T](BaseModel):
    data: T
    meta: ResponseMeta


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthStatus(BaseModel):
    status: str
    service: str
    environment: str
    checks: dict[str, str] = Field(default_factory=dict)
