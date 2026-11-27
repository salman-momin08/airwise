"use client";

/**
 * Smart pollution alert rule builder, quiet-hours configuration, and notification inbox.
 */

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  WorkspaceAuthOrErrorNotice,
  WorkspaceSkeleton,
} from "@/components/ui/workspace-state";
import {
  ALERT_TYPE_LABELS,
  ConfiguredAlertRulesSection,
  NotificationInboxSection,
} from "@/features/alerts/smart-alerts-sections";
import { alertsCommunityApi } from "@/lib/api/alerts-community";
import {
  createAlertRuleFormSchema,
  type CreateAlertRuleFormValues,
} from "@/lib/validation/alerts-community";
import { useLocationStore } from "@/stores/location-store";
import type { AlertChannel } from "@/types/alerts-community";

function CreateAlertRuleFormCard({
  form,
  watchQuietHours,
  isPending,
  onSubmit,
}: {
  form: ReturnType<typeof useForm<CreateAlertRuleFormValues>>;
  watchQuietHours: boolean;
  isPending: boolean;
  onSubmit: (vals: CreateAlertRuleFormValues) => void;
}) {
  const errors = form.formState.errors;
  return (
    <form
      onSubmit={form.handleSubmit(onSubmit)}
      className="space-y-4 rounded-card border border-border bg-surface p-6"
    >
      <h2 className="text-lg font-semibold">Create Standard-Isolated Smart Alert Rule</h2>
      <p className="text-xs text-text-secondary">
        India NAQI and US EPA breakpoints are strictly isolated. Unchanged AQI conditions never
        send duplicate spam, and external deliveries respect your local quiet hours.
      </p>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <label htmlFor="alert-city" className="block text-sm font-medium">
            City
          </label>
          <input
            id="alert-city"
            {...form.register("city")}
            aria-invalid={Boolean(errors.city)}
            className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
          />
          {errors.city ? (
            <p className="mt-1 text-xs text-red-700 dark:text-red-300">{errors.city.message}</p>
          ) : null}
        </div>

        <div>
          <label htmlFor="alert-type" className="block text-sm font-medium">
            Trigger Type
          </label>
          <select
            id="alert-type"
            {...form.register("alert_type")}
            className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
          >
            {Object.entries(ALERT_TYPE_LABELS).map(([val, label]) => (
              <option key={val} value={val}>
                {label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="alert-standard" className="block text-sm font-medium">
            AQI Standard
          </label>
          <select
            id="alert-standard"
            {...form.register("aqi_standard")}
            className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
          >
            <option value="india_naqi">India NAQI</option>
            <option value="us_epa">US EPA</option>
          </select>
        </div>

        <div>
          <label htmlFor="alert-threshold" className="block text-sm font-medium">
            AQI Threshold Value
          </label>
          <input
            id="alert-threshold"
            type="number"
            {...form.register("threshold_value")}
            className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
          />
        </div>

        <div>
          <label htmlFor="alert-cooldown" className="block text-sm font-medium">
            Cooldown Window (minutes)
          </label>
          <input
            id="alert-cooldown"
            type="number"
            {...form.register("cooldown_minutes")}
            className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
          />
        </div>

        <div>
          <label htmlFor="alert-timezone" className="block text-sm font-medium">
            Timezone (IANA)
          </label>
          <input
            id="alert-timezone"
            {...form.register("timezone")}
            className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
          />
          {errors.timezone ? (
            <p className="mt-1 text-xs text-red-700 dark:text-red-300">
              {errors.timezone.message}
            </p>
          ) : null}
        </div>
      </div>

      <div className="space-y-3 border-t border-border pt-4">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...form.register("enable_email")} />
          Deliver via Email in addition to In-App Inbox
        </label>

        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...form.register("enable_quiet_hours")} />
          Suppress chimes &amp; external deliveries during Quiet Hours
        </label>

        {watchQuietHours ? (
          <div className="grid max-w-md grid-cols-2 gap-4">
            <label className="text-xs font-medium">
              Quiet Hours Start (24h)
              <input
                {...form.register("quiet_hours_start")}
                placeholder="22:00"
                className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
              />
            </label>
            <label className="text-xs font-medium">
              Quiet Hours End (24h)
              <input
                {...form.register("quiet_hours_end")}
                placeholder="07:00"
                className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
              />
            </label>
            {errors.quiet_hours_end ? (
              <p className="col-span-2 text-xs text-red-700 dark:text-red-300">
                {errors.quiet_hours_end.message}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>

      <button
        type="submit"
        disabled={isPending}
        className="rounded bg-brand-primary px-4 py-2 text-sm font-semibold text-white dark:text-background disabled:opacity-60"
      >
        {isPending ? "Saving Rule..." : "Create Smart Alert Rule"}
      </button>
    </form>
  );
}

export function SmartAlertsWorkspace() {
  const queryClient = useQueryClient();
  const storeCity = useLocationStore((s) => s.selectedCity);
  const storeStandard = useLocationStore((s) => s.aqiStandard);
  const [statusBanner, setStatusBanner] = useState<string | null>(null);

  const rulesQuery = useQuery({
    queryKey: ["alerts", "rules"],
    queryFn: () => alertsCommunityApi.listAlertRules(),
    retry: false,
  });

  const notificationsQuery = useQuery({
    queryKey: ["alerts", "notifications"],
    queryFn: () => alertsCommunityApi.listNotifications(),
    enabled: rulesQuery.isSuccess,
    retry: false,
  });

  const form = useForm<CreateAlertRuleFormValues>({
    resolver: zodResolver(createAlertRuleFormSchema),
    defaultValues: {
      city: storeCity,
      alert_type: "aqi_threshold",
      aqi_standard: storeStandard,
      threshold_value: 200,
      enable_email: true,
      enable_quiet_hours: true,
      quiet_hours_start: "22:00",
      quiet_hours_end: "07:00",
      cooldown_minutes: 180,
      timezone: "Asia/Kolkata",
    },
  });

  const watchQuietHours = form.watch("enable_quiet_hours");

  const createMutation = useMutation({
    mutationFn: (values: CreateAlertRuleFormValues) => {
      const channels: AlertChannel[] = values.enable_email
        ? ["in_app", "email"]
        : ["in_app"];
      return alertsCommunityApi.createAlertRule({
        city: values.city,
        alert_type: values.alert_type,
        aqi_standard: values.aqi_standard,
        threshold_value: values.threshold_value,
        channels,
        quiet_hours_start: values.enable_quiet_hours ? values.quiet_hours_start : null,
        quiet_hours_end: values.enable_quiet_hours ? values.quiet_hours_end : null,
        cooldown_minutes: values.cooldown_minutes,
        timezone: values.timezone,
        is_enabled: true,
      });
    },
    onSuccess: async () => {
      setStatusBanner("Smart alert rule saved with anti-spam cooldown and quiet-hour safeguards.");
      await queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: (vars: { id: string; isEnabled: boolean }) =>
      alertsCommunityApi.updateAlertRule(vars.id, { is_enabled: vars.isEnabled }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["alerts", "rules"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (ruleId: string) => alertsCommunityApi.deleteAlertRule(ruleId),
    onSuccess: async () => {
      setStatusBanner("Alert rule removed.");
      await queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });

  const evaluateMutation = useMutation({
    mutationFn: () => alertsCommunityApi.evaluateMyAlerts(),
    onSuccess: async (res) => {
      const d = res.data;
      setStatusBanner(
        `Evaluated ${d.evaluated_rules} rule(s): ${d.triggered_notifications} triggered, ` +
          `${d.suppressed_duplicates_or_cooldown} duplicate/cooldown suppressed, ` +
          `${d.suppressed_quiet_hours_deliveries} delivery channel(s) suppressed by quiet hours.`,
      );
      await queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });

  const unsubscribeAllMutation = useMutation({
    mutationFn: () => alertsCommunityApi.unsubscribeAllAlerts(),
    onSuccess: async (res) => {
      setStatusBanner(
        `One-click opt-out completed: disabled ${res.data.disabled_rules_count} active alert rule(s).`,
      );
      await queryClient.invalidateQueries({ queryKey: ["alerts", "rules"] });
    },
  });

  const markReadMutation = useMutation({
    mutationFn: (id: string) => alertsCommunityApi.markNotificationRead(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["alerts", "notifications"] });
    },
  });

  const markAllReadMutation = useMutation({
    mutationFn: () => alertsCommunityApi.markAllNotificationsRead(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["alerts", "notifications"] });
    },
  });

  if (rulesQuery.isLoading) {
    return <WorkspaceSkeleton className="mt-6 h-60" />;
  }

  if (rulesQuery.isError) {
    return (
      <WorkspaceAuthOrErrorNotice
        error={rulesQuery.error}
        unauthPrompt="to configure smart pollution alerts, quiet hours, and notification channels."
        errorMessage="Unable to load your alert rules right now."
        onRetry={() => void rulesQuery.refetch()}
      />
    );
  }

  const rules = rulesQuery.data?.data ?? [];
  const notifications = notificationsQuery.data?.data ?? [];

  return (
    <div className="mt-6 space-y-6 text-text-primary">
      {statusBanner ? (
        <div
          role="status"
          className="rounded-lg border border-brand-primary/60 bg-brand-accent/40 px-4 py-3 text-sm font-medium"
        >
          {statusBanner}
        </div>
      ) : null}

      <CreateAlertRuleFormCard
        form={form}
        watchQuietHours={watchQuietHours}
        isPending={createMutation.isPending}
        onSubmit={(vals) => createMutation.mutate(vals)}
      />

      <ConfiguredAlertRulesSection
        rules={rules}
        evaluatePending={evaluateMutation.isPending}
        unsubscribePending={unsubscribeAllMutation.isPending}
        togglePending={toggleMutation.isPending}
        deletePending={deleteMutation.isPending}
        onEvaluate={() => evaluateMutation.mutate()}
        onUnsubscribeAll={() => unsubscribeAllMutation.mutate()}
        onToggleRule={(id, isEnabled) => toggleMutation.mutate({ id, isEnabled })}
        onDeleteRule={(id) => deleteMutation.mutate(id)}
      />

      <NotificationInboxSection
        notifications={notifications}
        markAllPending={markAllReadMutation.isPending}
        onMarkAllRead={() => markAllReadMutation.mutate()}
        onMarkRead={(id) => markReadMutation.mutate(id)}
      />
    </div>
  );
}
