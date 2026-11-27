import type {
  AlertRule,
  AlertType,
  NotificationItem,
} from "@/types/alerts-community";

export const ALERT_TYPE_LABELS: Record<AlertType, string> = {
  aqi_threshold: "AQI Threshold Breach",
  severe_smog_episode: "Severe Winter Smog Episode",
  forecast_deterioration: "24h Forecast Deterioration",
  clean_air_window: "Cleaner Outdoor Air Window",
  stale_telemetry_warning: "Stale / Delayed Telemetry Warning",
  daily_digest: "Daily Air Quality Digest",
};

function formatRuleSummary(rule: AlertRule): string {
  const stdText = rule.aqi_standard === "us_epa" ? "US EPA" : "India NAQI";
  const thresholdPart =
    rule.threshold_value !== null ? ` · Threshold ${rule.threshold_value}` : "";
  return `${rule.city} · ${ALERT_TYPE_LABELS[rule.alert_type]} (${stdText}${thresholdPart})`;
}

function formatRuleQuietHours(rule: AlertRule): string {
  if (rule.quiet_hours_start && rule.quiet_hours_end) {
    return `Quiet hours: ${rule.quiet_hours_start}–${rule.quiet_hours_end} (${rule.timezone})`;
  }
  return "Quiet hours off";
}

export function ConfiguredAlertRulesSection({
  rules,
  evaluatePending,
  unsubscribePending,
  togglePending,
  deletePending,
  onEvaluate,
  onUnsubscribeAll,
  onToggleRule,
  onDeleteRule,
}: {
  rules: AlertRule[];
  evaluatePending: boolean;
  unsubscribePending: boolean;
  togglePending: boolean;
  deletePending: boolean;
  onEvaluate: () => void;
  onUnsubscribeAll: () => void;
  onToggleRule: (id: string, nextEnabled: boolean) => void;
  onDeleteRule: (id: string) => void;
}) {
  return (
    <section
      aria-label="Configured alert rules"
      className="space-y-4 rounded-card border border-border bg-surface p-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold">Configured Alert Rules ({rules.length})</h2>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={evaluatePending || rules.length === 0}
            onClick={onEvaluate}
            className="rounded border border-text-secondary px-3 py-1.5 text-xs font-semibold disabled:opacity-50"
          >
            {evaluatePending ? "Evaluating..." : "Evaluate Active Rules Now"}
          </button>
          <button
            type="button"
            disabled={unsubscribePending || rules.length === 0}
            onClick={onUnsubscribeAll}
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
                <p className="font-semibold">{formatRuleSummary(rule)}</p>
                <p className="text-xs text-text-secondary">
                  Channels: {rule.channels.join(", ")} · Cooldown: {rule.cooldown_minutes} min ·{" "}
                  {formatRuleQuietHours(rule)}
                </p>
              </div>

              <div className="flex items-center gap-2 text-xs">
                <button
                  type="button"
                  disabled={togglePending}
                  onClick={() => onToggleRule(rule.id, !rule.is_enabled)}
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
                  disabled={deletePending}
                  onClick={() => onDeleteRule(rule.id)}
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
  );
}

export function NotificationInboxSection({
  notifications,
  markAllPending,
  onMarkAllRead,
  onMarkRead,
}: {
  notifications: NotificationItem[];
  markAllPending: boolean;
  onMarkAllRead: () => void;
  onMarkRead: (id: string) => void;
}) {
  const hasUnread = notifications.some((n) => n.read_at === null);
  return (
    <section
      aria-label="Notification inbox and delivery history"
      className="space-y-4 rounded-card border border-border bg-surface p-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold">
          Notification Inbox &amp; Delivery Audit ({notifications.length})
        </h2>
        {hasUnread ? (
          <button
            type="button"
            disabled={markAllPending}
            onClick={onMarkAllRead}
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
            <li key={notif.id} className="space-y-2 rounded-lg border border-border p-4">
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
                    onClick={() => onMarkRead(notif.id)}
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
  );
}
