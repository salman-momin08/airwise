"use client";

import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { alertsCommunityApi } from "@/lib/api/alerts-community";
import { ApiClientError } from "@/lib/api/client";
import {
  createAlertRuleFormSchema,
  type CreateAlertRuleFormValues,
} from "@/lib/validation/alerts-community";
import { useLocationStore } from "@/stores/location-store";
import type { AlertChannel, AlertType } from "@/types/alerts-community";

const ALERT_TYPE_LABELS: Record<AlertType, string> = {
  aqi_threshold: "AQI Threshold Breach",
  severe_smog_episode: "Severe Winter Smog Episode",
  forecast_deterioration: "24h Forecast Deterioration",
  clean_air_window: "Cleaner Outdoor Air Window",
  stale_telemetry_warning: "Stale / Delayed Telemetry Warning",
  daily_digest: "Daily Air Quality Digest",
};

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
    return (
      <div
        aria-busy="true"
        className="mt-6 h-60 animate-pulse rounded-card border border-border bg-surface p-6"
      />
    );
  }

  if (rulesQuery.isError) {
    const unauth =
      rulesQuery.error instanceof ApiClientError && rulesQuery.error.status === 401;
    return (
      <div role="alert" className="mt-6 rounded-card border border-border bg-surface p-6 text-sm">
        {unauth ? (
          <p>
            Please{" "}
            <Link href="/login" className="font-semibold text-brand-primary underline">
              sign in
            </Link>{" "}
            to configure smart pollution alerts, quiet hours, and notification channels.
          </p>
        ) : (
          <div className="space-y-3">
            <p>Unable to load your alert rules right now.</p>
            <button
              type="button"
              onClick={() => void rulesQuery.refetch()}
              className="rounded border border-text-secondary px-3 py-1.5 font-medium"
            >
              Retry
            </button>
          </div>
        )}
      </div>
    );
  }

  const errors = form.formState.errors;
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

      <form
        onSubmit={form.handleSubmit((vals) => createMutation.mutate(vals))}
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
          disabled={createMutation.isPending}
          className="rounded bg-brand-primary px-4 py-2 text-sm font-semibold text-white dark:text-background disabled:opacity-60"
        >
          {createMutation.isPending ? "Saving Rule..." : "Create Smart Alert Rule"}
        </button>
      </form>

      <section
        aria-label="Configured alert rules"
        className="space-y-4 rounded-card border border-border bg-surface p-6"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-base font-semibold">Configured Alert Rules ({rules.length})</h2>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={evaluateMutation.isPending || rules.length === 0}
              onClick={() => evaluateMutation.mutate()}
              className="rounded border border-text-secondary px-3 py-1.5 text-xs font-semibold disabled:opacity-50"
            >
              {evaluateMutation.isPending ? "Evaluating..." : "Evaluate Active Rules Now"}
            </button>
            <button
              type="button"
              disabled={unsubscribeAllMutation.isPending || rules.length === 0}
              onClick={() => unsubscribeAllMutation.mutate()}
              className="rounded border border-text-secondary px-3 py-1.5 text-xs font-medium disabled:opacity-50"
            >
              One-Click Opt-Out All
            </button>
          </div>
        </div>

        {rules.length === 0 ? (
          <p className="text-sm text-text-secondary">
            No alert rules configured yet. Create a threshold or clean-window rule above.
          </p>
        ) : (
          <ul className="space-y-3">
            {rules.map((rule) => (
              <li
                key={rule.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border p-4 text-sm"
              >
                <div className="space-y-1">
                  <p className="font-semibold">
                    {rule.city} · {ALERT_TYPE_LABELS[rule.alert_type]} (
                    {rule.aqi_standard === "us_epa" ? "US EPA" : "India NAQI"}
                    {rule.threshold_value !== null ? ` · Threshold ${rule.threshold_value}` : ""})
                  </p>
                  <p className="text-xs text-text-secondary">
                    Channels: {rule.channels.join(", ")} · Cooldown: {rule.cooldown_minutes} min ·{" "}
                    {rule.quiet_hours_start && rule.quiet_hours_end
                      ? `Quiet hours: ${rule.quiet_hours_start}–${rule.quiet_hours_end} (${rule.timezone})`
                      : "Quiet hours off"}
                  </p>
                </div>

                <div className="flex items-center gap-2 text-xs">
                  <button
                    type="button"
                    disabled={toggleMutation.isPending}
                    onClick={() =>
                      toggleMutation.mutate({ id: rule.id, isEnabled: !rule.is_enabled })
                    }
                    className={`rounded border px-3 py-1 font-semibold ${
                      rule.is_enabled
                        ? "border-brand-primary bg-brand-accent/50 text-text-primary"
                        : "border-text-secondary text-text-secondary"
                    }`}
                  >
                    {rule.is_enabled ? "Enabled (Pause)" : "Paused (Enable)"}
                  </button>
                  <button
                    type="button"
                    disabled={deleteMutation.isPending}
                    onClick={() => deleteMutation.mutate(rule.id)}
                    className="rounded border border-text-secondary px-3 py-1"
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section
        aria-label="Notification inbox and delivery history"
        className="space-y-4 rounded-card border border-border bg-surface p-6"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-base font-semibold">
            Notification Inbox &amp; Delivery Audit ({notifications.length})
          </h2>
          {notifications.some((n) => n.read_at === null) ? (
            <button
              type="button"
              disabled={markAllReadMutation.isPending}
              onClick={() => markAllReadMutation.mutate()}
              className="rounded border border-text-secondary px-3 py-1 text-xs font-medium"
            >
              Mark All Read
            </button>
          ) : null}
        </div>

        {notifications.length === 0 ? (
          <p className="text-sm text-text-secondary">
            No notifications triggered yet. Evaluate your active rules or wait for scheduled
            15-minute telemetry checks.
          </p>
        ) : (
          <ul className="space-y-3 text-sm">
            {notifications.map((notif) => (
              <li
                key={notif.id}
                className="space-y-2 rounded-lg border border-border p-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-semibold text-text-primary">
                    {notif.read_at === null ? "● " : ""}
                    {notif.title}
                  </p>
                  <span className="text-xs text-text-secondary">
                    {new Date(notif.created_at).toLocaleString()}
                  </span>
                </div>
                <p className="text-xs text-text-secondary">{notif.body}</p>
                <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-xs">
                  <div className="flex flex-wrap gap-2">
                    {notif.deliveries.map((d) => (
                      <span
                        key={d.id}
                        className="rounded-full border border-border px-2.5 py-0.5 text-text-secondary"
                      >
                        {d.channel}: <strong className="text-text-primary">{d.status}</strong>
                      </span>
                    ))}
                  </div>
                  {notif.read_at === null ? (
                    <button
                      type="button"
                      onClick={() => markReadMutation.mutate(notif.id)}
                      className="text-brand-primary underline"
                    >
                      Mark read
                    </button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
