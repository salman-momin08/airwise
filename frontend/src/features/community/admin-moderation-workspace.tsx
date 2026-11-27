"use client";

/**
 * Moderator and administrator abuse-report review and resolution workspace.
 */

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { alertsCommunityApi } from "@/lib/api/alerts-community";
import { ApiClientError } from "@/lib/api/client";
import type { ReportResolutionStatus } from "@/types/alerts-community";

export function AdminModerationWorkspace() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<ReportResolutionStatus | "all">("open");
  const [notesById, setNotesById] = useState<Record<string, string>>({});

  const reportsQuery = useQuery({
    queryKey: ["admin", "community", "reports", statusFilter],
    queryFn: () =>
      alertsCommunityApi.listModerationReports(
        statusFilter === "all" ? undefined : statusFilter,
      ),
    retry: false,
  });

  const resolveMutation = useMutation({
    mutationFn: (vars: {
      reportId: string;
      action: "dismiss" | "hide_initiative";
      note: string;
    }) =>
      alertsCommunityApi.resolveModerationReport(vars.reportId, {
        action: vars.action,
        resolution_note: vars.note,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin", "community", "reports"] });
    },
  });

  if (reportsQuery.isLoading) {
    return (
      <div
        aria-busy="true"
        className="mt-6 h-48 animate-pulse rounded-card border border-border bg-surface p-6"
      />
    );
  }

  if (reportsQuery.isError) {
    const err = reportsQuery.error;
    const isAuthError =
      err instanceof ApiClientError && (err.status === 401 || err.status === 403);
    return (
      <div role="alert" className="mt-6 rounded-card border border-border bg-surface p-6 text-sm">
        {isAuthError ? (
          <p>
            Moderator or Administrator privileges are required to inspect the community moderation
            queue.{" "}
            <Link href="/dashboard/community" className="text-brand-primary underline">
              Return to Community Hub
            </Link>
            .
          </p>
        ) : (
          <button
            type="button"
            onClick={() => void reportsQuery.refetch()}
            className="rounded border border-text-secondary px-3 py-1.5 font-medium"
          >
            Retry Moderation Queue
          </button>
        )}
      </div>
    );
  }

  const reports = reportsQuery.data?.data ?? [];

  return (
    <div className="mt-6 space-y-5 text-text-primary">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-border bg-surface p-4">
        <label className="text-sm font-medium">
          Queue Filter
          <select
            value={statusFilter}
            onChange={(e) =>
              setStatusFilter(e.target.value as ReportResolutionStatus | "all")
            }
            className="ml-2 rounded border border-text-secondary bg-surface p-2 text-sm"
          >
            <option value="open">Open Reports</option>
            <option value="resolved_removed">Resolved (Hidden)</option>
            <option value="dismissed">Dismissed</option>
            <option value="all">All Reports</option>
          </select>
        </label>
        <span className="text-xs text-text-secondary">
          Every moderation decision is recorded in append-only audit_logs.
        </span>
      </div>

      {reports.length === 0 ? (
        <p className="rounded-card border border-border bg-surface p-6 text-sm text-text-secondary">
          No community moderation reports match the selected filter.
        </p>
      ) : (
        <ul className="space-y-4">
          {reports.map((report) => {
            const noteVal =
              notesById[report.id] ?? "Reviewed against AirWise privacy & safety policy.";
            return (
              <li
                key={report.id}
                className="space-y-3 rounded-card border border-border bg-surface p-5 text-sm"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-semibold uppercase text-brand-primary">
                    {report.reason_category.replaceAll("_", " ")}
                  </span>
                  <span className="text-xs text-text-secondary">
                    Status: <strong>{report.status}</strong> ·{" "}
                    {new Date(report.created_at).toLocaleString()}
                  </span>
                </div>
                <p>{report.details}</p>

                {report.status === "open" ? (
                  <div className="space-y-2 border-t border-border pt-3">
                    <label className="block text-xs font-medium">
                      Moderator Resolution Note
                      <input
                        value={noteVal}
                        onChange={(e) =>
                          setNotesById((prev) => ({ ...prev, [report.id]: e.target.value }))
                        }
                        className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-xs"
                      />
                    </label>
                    <div className="flex flex-wrap gap-2">
                      {report.initiative_id ? (
                        <button
                          type="button"
                          disabled={resolveMutation.isPending}
                          onClick={() =>
                            resolveMutation.mutate({
                              reportId: report.id,
                              action: "hide_initiative",
                              note: noteVal,
                            })
                          }
                          className="rounded bg-brand-primary px-3 py-1.5 text-xs font-semibold text-white dark:text-background"
                        >
                          Hide Initiative &amp; Resolve
                        </button>
                      ) : null}
                      <button
                        type="button"
                        disabled={resolveMutation.isPending}
                        onClick={() =>
                          resolveMutation.mutate({
                            reportId: report.id,
                            action: "dismiss",
                            note: noteVal,
                          })
                        }
                        className="rounded border border-text-secondary px-3 py-1.5 text-xs font-medium"
                      >
                        Dismiss Report
                      </button>
                    </div>
                  </div>
                ) : report.resolution_note ? (
                  <p className="text-xs text-text-secondary">
                    <strong>Resolution:</strong> {report.resolution_note}
                  </p>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
