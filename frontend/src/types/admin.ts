/**
 * TypeScript DTO contracts for administrative governance, audit logs, and AI monitoring.
 */

export type AdminAssignableRole = "user" | "moderator" | "admin";

export interface AdminOverview {
  active_users_count: number;
  enabled_data_sources_count: number;
  ingested_documents_count: number;
  knowledge_chunks_count: number;
  total_ai_generations: number;
  ai_fallback_rate: number;
  open_moderation_reports_count: number;
  audit_log_entries_count: number;
  active_aqi_provider_mode: string;
  active_llm_provider: string;
}

export interface AdminUserItem {
  id: string;
  email: string;
  display_name: string;
  role: string;
  is_active: boolean;
  is_email_verified: boolean;
  created_at: string;
}

export interface AdminDataSourceItem {
  id: string;
  slug: string;
  name: string;
  provider_type: string;
  license_note: string | null;
  refresh_interval_seconds: number;
  is_enabled: boolean;
  priority_rank: number;
}

export interface AdminKnowledgeDocumentItem {
  id: string;
  title: string;
  publisher: string;
  source_url: string;
  jurisdiction: string;
  trust_classification: string;
  publication_date: string | null;
  last_reviewed_date: string;
  chunks_count: number;
  is_review_overdue: boolean;
}

export interface AdminIngestionJobItem {
  id: string;
  source_url: string;
  status: string;
  error_code: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface AdminKnowledgeGovernance {
  documents: AdminKnowledgeDocumentItem[];
  recent_jobs: AdminIngestionJobItem[];
}

export interface AdminAIMonitoring {
  total_generations: number;
  fallback_generations: number;
  fallback_rate: number;
  total_tokens: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  fallback_reasons: Record<string, number>;
  tool_invocations: Record<string, number>;
  runtime_http_p95_ms: number;
  runtime_aqi_cache_hits: number;
  runtime_aqi_cache_misses: number;
}

export interface AdminAuditLogItem {
  id: string;
  actor_user_id: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  metadata_redacted: Record<string, unknown>;
  created_at: string;
}

export interface SystemSettingItem {
  key: string;
  value: Record<string, unknown>;
  updated_by: string | null;
  updated_at: string;
}
