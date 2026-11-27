/**
 * Typed `/api/v1/alerts/*`, `/api/v1/notifications/*`, and `/api/v1/communities/*` client methods.
 */

import { apiRequest } from "@/lib/api/client";
import type { AQIStandard } from "@/types/api";
import type {
  AbuseReport,
  AlertChannel,
  AlertEvaluationSummary,
  AlertRule,
  AlertType,
  ChallengeType,
  CommunityDetail,
  CommunityInitiative,
  CommunitySummary,
  NotificationItem,
  ParticipationReceipt,
  ReportReason,
  ReportResolutionStatus,
} from "@/types/alerts-community";

export const alertsCommunityApi = {
  listAlertRules: () => apiRequest<AlertRule[]>("/alerts"),

  createAlertRule: (payload: {
    city: string;
    alert_type: AlertType;
    aqi_standard: AQIStandard;
    threshold_value?: number | null;
    channels: AlertChannel[];
    quiet_hours_start?: string | null;
    quiet_hours_end?: string | null;
    cooldown_minutes: number;
    timezone: string;
    is_enabled?: boolean;
  }) =>
    apiRequest<AlertRule>("/alerts", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateAlertRule: (
    ruleId: string,
    payload: {
      is_enabled?: boolean;
      threshold_value?: number;
      cooldown_minutes?: number;
      quiet_hours_start?: string;
      quiet_hours_end?: string;
      clear_quiet_hours?: boolean;
    },
  ) =>
    apiRequest<AlertRule>(`/alerts/${ruleId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  deleteAlertRule: (ruleId: string) =>
    apiRequest<{ status: string }>(`/alerts/${ruleId}`, {
      method: "DELETE",
    }),

  evaluateMyAlerts: () =>
    apiRequest<AlertEvaluationSummary>("/alerts/evaluate", {
      method: "POST",
    }),

  unsubscribeAllAlerts: () =>
    apiRequest<{ disabled_rules_count: number }>("/alerts/unsubscribe-all", {
      method: "POST",
    }),

  listNotifications: () => apiRequest<NotificationItem[]>("/notifications"),

  markNotificationRead: (notificationId: string) =>
    apiRequest<NotificationItem>(`/notifications/${notificationId}/read`, {
      method: "PATCH",
    }),

  markAllNotificationsRead: () =>
    apiRequest<{ marked_read_count: number }>("/notifications/read-all", {
      method: "POST",
    }),

  listCommunities: (city?: string) =>
    apiRequest<CommunitySummary[]>(
      city ? `/communities?city=${encodeURIComponent(city)}` : "/communities",
    ),

  getCommunityDetail: (communityId: string) =>
    apiRequest<CommunityDetail>(`/communities/${communityId}`),

  createCommunity: (payload: {
    slug: string;
    name: string;
    city: string;
    coarse_boundary_label: string;
    description: string;
  }) =>
    apiRequest<CommunityDetail>("/communities", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  joinCommunity: (communityId: string, publicDisplayConsent: boolean) =>
    apiRequest<CommunityDetail>(`/communities/${communityId}/join`, {
      method: "POST",
      body: JSON.stringify({ public_display_consent: publicDisplayConsent }),
    }),

  leaveCommunity: (communityId: string) =>
    apiRequest<{ status: string }>(`/communities/${communityId}/leave`, {
      method: "POST",
    }),

  listInitiatives: (communityId: string) =>
    apiRequest<CommunityInitiative[]>(`/communities/${communityId}/initiatives`),

  createInitiative: (
    communityId: string,
    payload: {
      title: string;
      description: string;
      challenge_type: ChallengeType;
      starts_at: string;
      ends_at: string;
    },
  ) =>
    apiRequest<CommunityInitiative>(`/communities/${communityId}/initiatives`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  logParticipation: (
    communityId: string,
    initiativeId: string,
    payload: {
      self_reported_actions_count: number;
      commute_distance_saved_km: number;
      note?: string;
    },
  ) =>
    apiRequest<ParticipationReceipt>(
      `/communities/${communityId}/initiatives/${initiativeId}/participate`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),

  submitAbuseReport: (
    communityId: string,
    payload: {
      initiative_id?: string | null;
      reason_category: ReportReason;
      details: string;
    },
  ) =>
    apiRequest<AbuseReport>(`/communities/${communityId}/reports`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listModerationReports: (status?: ReportResolutionStatus) =>
    apiRequest<AbuseReport[]>(
      status ? `/admin/community/reports?status=${encodeURIComponent(status)}` : "/admin/community/reports",
    ),

  resolveModerationReport: (
    reportId: string,
    payload: { action: "dismiss" | "hide_initiative"; resolution_note: string },
  ) =>
    apiRequest<AbuseReport>(`/admin/community/reports/${reportId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
};
