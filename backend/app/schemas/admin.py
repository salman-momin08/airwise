"""Pydantic v2 DTOs for administrative overview, user governance, data sources, and audit logs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AdminAssignableRole = Literal["user", "moderator", "admin"]


class AdminOverviewSchema(BaseModel):
    active_users_count: int
    enabled_data_sources_count: int
    ingested_documents_count: int
    knowledge_chunks_count: int
    total_ai_generations: int
    ai_fallback_rate: float
    open_moderation_reports_count: int
    audit_log_entries_count: int
    active_aqi_provider_mode: str
    active_llm_provider: str


class AdminUserItemSchema(BaseModel):
    id: UUID
    email: str
    display_name: str
    role: str
    is_active: bool
    is_email_verified: bool
    created_at: datetime


class AdminUpdateUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: AdminAssignableRole | None = None
    is_active: bool | None = None


class AdminDataSourceItemSchema(BaseModel):
    id: UUID
    slug: str
    name: str
    provider_type: str
    license_note: str | None = None
    refresh_interval_seconds: int
    is_enabled: bool
    priority_rank: int


class AdminUpdateDataSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_enabled: bool | None = None
    priority_rank: int | None = Field(default=None, ge=1, le=100)
    refresh_interval_seconds: int | None = Field(default=None, ge=60, le=86400)


class AdminKnowledgeDocumentItemSchema(BaseModel):
    id: UUID
    title: str
    publisher: str
    source_url: str
    jurisdiction: str
    trust_classification: str
    publication_date: datetime | None = None
    last_reviewed_date: datetime
    chunks_count: int
    is_review_overdue: bool


class AdminIngestionJobItemSchema(BaseModel):
    id: UUID
    source_url: str
    status: str
    error_code: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class AdminKnowledgeGovernanceSchema(BaseModel):
    documents: list[AdminKnowledgeDocumentItemSchema]
    recent_jobs: list[AdminIngestionJobItemSchema]


class AdminAIMonitoringSchema(BaseModel):
    total_generations: int
    fallback_generations: int
    fallback_rate: float
    total_tokens: int
    avg_latency_ms: float
    p95_latency_ms: float
    fallback_reasons: dict[str, int]
    tool_invocations: dict[str, int]
    runtime_http_p95_ms: float
    runtime_aqi_cache_hits: int
    runtime_aqi_cache_misses: int


class AdminAuditLogItemSchema(BaseModel):
    id: UUID
    actor_user_id: str | None = None
    action: str
    target_type: str
    target_id: str | None = None
    metadata_redacted: dict[str, Any]
    created_at: datetime


class SystemSettingItemSchema(BaseModel):
    key: str
    value: dict[str, Any]
    updated_by: str | None = None
    updated_at: datetime


class UpsertSystemSettingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: dict[str, Any]
