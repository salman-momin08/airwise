"use client";

/**
 * Chronological user environmental action log and cumulative estimated impact summary.
 */

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  WorkspaceAuthOrErrorNotice,
  WorkspaceSkeleton,
} from "@/components/ui/workspace-state";
import { alertsCommunityApi } from "@/lib/api/alerts-community";
import { planningApi } from "@/lib/api/planning";

function HistoryCardSection({
  title,
  linkHref,
  linkLabel,
  emptyText,
  items,
}: {
  title: string;
  linkHref: string;
  linkLabel: string;
  emptyText: string;
  items: Array<{ id: string; primary: string; secondary: string }>;
}) {
  return (
    <section className="space-y-3 rounded-card border border-border bg-surface p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-text-primary">
          {title} ({items.length})
        </h2>
        <Link href={linkHref} className="text-xs text-brand-primary underline">
          {linkLabel}
        </Link>
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-text-secondary">{emptyText}</p>
      ) : (
        <ul className="space-y-2 text-xs">
          {items.slice(0, 10).map((item) => (
            <li key={item.id} className="rounded border border-border p-3">
              <p className="font-semibold text-text-primary">{item.primary}</p>
              <p className="text-text-secondary">{item.secondary}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

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
    return <WorkspaceSkeleton className="mt-6 h-56" />;
  }

  if (routinesQuery.isError) {
    return (
      <WorkspaceAuthOrErrorNotice
        error={routinesQuery.error}
        unauthPrompt="to inspect your saved daily routines, logged actions, and alert history."
        errorMessage="Unable to load your activity history right now."
        onRetry={() => void routinesQuery.refetch()}
        retryLabel="Retry History"
      />
    );
  }

  const routineItems = (routinesQuery.data?.data ?? []).map((r) => ({
    id: r.id,
    primary: `${r.plan_date} · ${r.city} (${r.status.toUpperCase()})`,
    secondary: `${r.activities.length} time-slotted blocks · ${
      r.aqi_standard === "us_epa" ? "US EPA" : "India NAQI"
    }`,
  }));
  const actionItems = (actionsQuery.data?.data ?? []).map((a) => ({
    id: a.id,
    primary: a.title,
    secondary: `${a.quantity} ${a.unit} · ${new Date(a.occurred_at).toLocaleDateString()}`,
  }));
  const notificationItems = (notificationsQuery.data?.data ?? []).map((n) => ({
    id: n.id,
    primary: n.title,
    secondary: new Date(n.created_at).toLocaleString(),
  }));

  return (
    <div className="mt-6 grid gap-6 lg:grid-cols-3">
      <HistoryCardSection
        title="Saved Routines"
        linkHref="/dashboard/routine-planner"
        linkLabel="Planner"
        emptyText="No saved routines yet."
        items={routineItems}
      />
      <HistoryCardSection
        title="Logged Actions"
        linkHref="/dashboard/impact"
        linkLabel="Impact Tracker"
        emptyText="No self-reported actions logged yet."
        items={actionItems}
      />
      <HistoryCardSection
        title="Alert Logs"
        linkHref="/dashboard/alerts"
        linkLabel="Smart Alerts"
        emptyText="No alert notifications triggered yet."
        items={notificationItems}
      />
    </div>
  );
}
