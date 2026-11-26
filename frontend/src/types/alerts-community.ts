import type { AQIStandard } from "@/types/api";

export type AlertType =
  | "aqi_threshold"
  | "severe_smog_episode"
  | "forecast_deterioration"
  | "clean_air_window"
  | "stale_telemetry_warning"
  | "daily_digest";

export type AlertChannel = "in_app" | "email" | "web_push";

export type NotificationSeverity = "info" | "warning" | "critical";

export type DeliveryStatus =
  | "pending"
  | "sent"
  | "failed"
  | "suppressed_quiet_hours"
  | "unconfigured_channel";

export interface AlertRule {
  id: string;
  location_id: string | null;
  city: string;
  alert_type: AlertType;
  aqi_standard: AQIStandard;
  threshold_value: number | null;
  channels: AlertChannel[];
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
  cooldown_minutes: number;
  timezone: string;
  is_enabled: boolean;
  last_triggered_at: string | null;
  created_at: string;
}

export interface NotificationDelivery {
  id: string;
  channel: AlertChannel;
  status: DeliveryStatus;
  provider_message_id: string | null;
  attempt_count: number;
  delivered_at: string | null;
}

export interface NotificationItem {
  id: string;
  alert_rule_id: string | null;
  title: string;
  body: string;
  severity: NotificationSeverity;
  dedup_key: string;
  read_at: string | null;
  created_at: string;
  deliveries: NotificationDelivery[];
}

export interface AlertEvaluationSummary {
  evaluated_rules: number;
  triggered_notifications: number;
  suppressed_duplicates_or_cooldown: number;
  suppressed_quiet_hours_deliveries: number;
}

export type ChallengeType =
  | "no_idling_school_week"
  | "public_transit_challenge"
  | "carpool_corridor"
  | "clean_cooking_awareness"
  | "indoor_clean_air_drive";

export type ModerationStatus = "pending_review" | "active" | "hidden" | "archived";

export type ReportReason =
  | "pii_exposure"
  | "misinformation"
  | "unsafe_health_advice"
  | "harassment_or_spam";

export type ReportResolutionStatus = "open" | "resolved_removed" | "dismissed";

export interface CommunitySummary {
  id: string;
  slug: string;
  name: string;
  city: string;
  coarse_boundary_label: string;
  description: string;
  member_count: number;
  active_initiatives_count: number;
  is_current_user_member: boolean;
  current_user_public_display_consent: boolean;
  created_at: string;
}

export interface CommunityDetail extends CommunitySummary {
  moderation_policy: string;
  total_self_reported_actions: number;
  total_estimated_avoided_co2e_kg: number;
  consented_member_display_names: string[];
  privacy_and_methodology_notice: string;
}

export interface CommunityInitiative {
  id: string;
  community_id: string;
  community_name: string | null;
  city: string | null;
  title: string;
  description: string;
  challenge_type: ChallengeType;
  starts_at: string;
  ends_at: string;
  moderation_status: ModerationStatus;
  participant_entries_count: number;
  total_self_reported_actions: number;
  total_estimated_avoided_co2e_kg: number;
  is_self_reported_aggregate: true;
  created_at: string;
}

export interface ParticipationReceipt {
  id: string;
  initiative_id: string;
  self_reported_actions_count: number;
  estimated_avoided_co2e_kg: number;
  is_self_reported: true;
  is_estimate: true;
  reported_at: string;
}

export interface AbuseReport {
  id: string;
  community_id: string;
  initiative_id: string | null;
  reason_category: ReportReason;
  details: string;
  status: ReportResolutionStatus;
  resolution_note: string | null;
  created_at: string;
  resolved_at: string | null;
}
