"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { alertsCommunityApi } from "@/lib/api/alerts-community";
import { ApiClientError } from "@/lib/api/client";
import { planningApi } from "@/lib/api/planning";

export function ActivityHistoryWorkspace() {
  const routinesQuery = useQuery({
    queryKey: ["routines", "list"],
    queryFn: () => planningApi.listRoutines(),
    retry: false,
  });

  const actionsQuery = useQuery({
    queryKey: ["impact", "history"],
    queryFn: () => planningApi.getImpactHistory(),
    enabled: routinesQuery.isSuccess,
    retry: false,
  });

  const notificationsQuery = useQuery({
    queryKey: ["alerts", "notifications"],
    queryFn: () => alertsCommunityApi.listNotifications(),
    enabled: routinesQuery.isSuccess,
    retry: false,
  });

  if (routinesQuery.isLoading) {
    return (
      <div
        aria-busy="true"
        className="mt-6 h-56 animate-pulse rounded-card border border-border bg-surface p-6"
      />
    );
  }

  if (routinesQuery.isError) {
    const unauth =
      routinesQuery.error instanceof ApiClientError &&
      routinesQuery.error.status === 401;
    return (
      <div role="alert" className="mt-6 rounded-card border border-border bg-surface p-6 text-sm">
        {unauth ? (
          <p>
            Please{" "}
            <Link href="/login" className="font-semibold text-brand-primary underline">
              sign in
            </Link>{" "}
            to inspect your saved daily routines, logged actions, and alert history.
          </p>
        ) : (
          <button
            type="button"
            onClick={() => void routinesQuery.refetch()}
            className="rounded border border-text-secondary px-3 py-1.5 font-medium"
          >
            Retry History
          </button>
        )}
      </div>
    );
  }

  const routines = routinesQuery.data?.data ?? [];
  const actions = actionsQuery.data?.data ?? [];
  const notifications = notificationsQuery.data?.data ?? [];

  return (
    <div className="mt-6 grid gap-6 lg:grid-cols-3">
      <section className="space-y-3 rounded-card border border-border bg-surface p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-text-primary">
            Saved Routines ({routines.length})
          </h2>
          <Link
            href="/dashboard/routine-planner"
            className="text-xs text-brand-primary underline"
          >
            Planner
          </Link>
        </div>
        {routines.length === 0 ? (
          <p className="text-xs text-text-secondary">No saved routines yet.</p>
        ) : (
          <ul className="space-y-2 text-xs">
            {routines.slice(0, 10).map((r) => (
              <li key={r.id} className="rounded border border-border p-3">
                <p className="font-semibold text-text-primary">
                  {r.plan_date} · {r.city} ({r.status.toUpperCase()})
                </p>
                <p className="text-text-secondary">
                  {r.activities.length} time-slotted blocks ·{" "}
                  {r.aqi_standard === "us_epa" ? "US EPA" : "India NAQI"}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-3 rounded-card border border-border bg-surface p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-text-primary">
            Logged Actions ({actions.length})
          </h2>
          <Link href="/dashboard/impact" className="text-xs text-brand-primary underline">
            Impact Tracker
          </Link>
        </div>
        {actions.length === 0 ? (
          <p className="text-xs text-text-secondary">No self-reported actions logged yet.</p>
        ) : (
          <ul className="space-y-2 text-xs">
            {actions.slice(0, 10).map((a) => (
              <li key={a.id} className="rounded border border-border p-3">
                <p className="font-semibold text-text-primary">{a.title}</p>
                <p className="text-text-secondary">
                  {a.quantity} {a.unit} · {new Date(a.occurred_at).toLocaleDateString()}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-3 rounded-card border border-border bg-surface p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-text-primary">
            Alert Logs ({notifications.length})
          </h2>
          <Link href="/dashboard/alerts" className="text-xs text-brand-primary underline">
            Smart Alerts
          </Link>
        </div>
        {notifications.length === 0 ? (
          <p className="text-xs text-text-secondary">No alert notifications triggered yet.</p>
        ) : (
          <ul className="space-y-2 text-xs">
            {notifications.slice(0, 10).map((n) => (
              <li key={n.id} className="rounded border border-border p-3">
                <p className="font-semibold text-text-primary">{n.title}</p>
                <p className="text-text-secondary">
                  {new Date(n.created_at).toLocaleString()}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
