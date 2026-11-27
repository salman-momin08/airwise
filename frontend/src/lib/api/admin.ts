/**
 * Typed `/api/v1/admin/*` API client methods for platform governance.
 */

import { apiRequest } from "@/lib/api/client";
import type {
  AdminAIMonitoring,
  AdminAssignableRole,
  AdminAuditLogItem,
  AdminDataSourceItem,
  AdminKnowledgeGovernance,
  AdminOverview,
  AdminUserItem,
  SystemSettingItem,
} from "@/types/admin";

export const adminApi = {
  getOverview: () => apiRequest<AdminOverview>("/admin/overview"),

  listUsers: () => apiRequest<AdminUserItem[]>("/admin/users"),

  updateUser: (
    userId: string,
    payload: { role?: AdminAssignableRole; is_active?: boolean },
  ) =>
    apiRequest<AdminUserItem>(`/admin/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  listDataSources: () => apiRequest<AdminDataSourceItem[]>("/admin/data-sources"),

  seedDefaultDataSources: () =>
    apiRequest<AdminDataSourceItem[]>("/admin/data-sources/seed-defaults", {
      method: "POST",
    }),

  updateDataSource: (
    sourceId: string,
    payload: {
      is_enabled?: boolean;
      priority_rank?: number;
      refresh_interval_seconds?: number;
    },
  ) =>
    apiRequest<AdminDataSourceItem>(`/admin/data-sources/${sourceId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  getKnowledgeGovernance: () =>
    apiRequest<AdminKnowledgeGovernance>("/admin/knowledge-base"),

  getAIMonitoring: () => apiRequest<AdminAIMonitoring>("/admin/ai-monitoring"),

  listAuditLogs: (actionPrefix?: string) =>
    apiRequest<AdminAuditLogItem[]>(
      actionPrefix
        ? `/admin/audit-logs?action_prefix=${encodeURIComponent(actionPrefix)}`
        : "/admin/audit-logs",
    ),

  listSystemSettings: () => apiRequest<SystemSettingItem[]>("/admin/settings"),

  upsertSystemSetting: (key: string, value: Record<string, unknown>) =>
    apiRequest<SystemSettingItem>(`/admin/settings/${encodeURIComponent(key)}`, {
      method: "PUT",
      body: JSON.stringify({ value }),
    }),
};
