"use client";

/**
 * Administrative platform overview metrics, runtime advisories, and RBAC user management.
 */

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adminApi } from "@/lib/api/admin";
import { ApiClientError } from "@/lib/api/client";
import type { AdminAssignableRole } from "@/types/admin";

export function AdminOverviewWorkspace() {
  const queryClient = useQueryClient();
  const [bannerText, setBannerText] = useState("");

  const overviewQuery = useQuery({
    queryKey: ["admin", "overview"],
    queryFn: () => adminApi.getOverview(),
    retry: false,
  });

  const settingsQuery = useQuery({
    queryKey: ["admin", "settings"],
    queryFn: () => adminApi.listSystemSettings(),
    enabled: overviewQuery.isSuccess,
    retry: false,
  });

  const settingMutation = useMutation({
    mutationFn: () =>
      adminApi.upsertSystemSetting("platform_notice", {
        banner: bannerText.trim(),
        active: Boolean(bannerText.trim()),
      }),
    onSuccess: async () => {
      setBannerText("");
      await queryClient.invalidateQueries({ queryKey: ["admin"] });
    },
  });

  if (overviewQuery.isLoading) {
    return (
      <div
        aria-busy="true"
        className="mt-6 h-48 animate-pulse rounded-card border border-border bg-surface p-6"
      />
    );
  }

  if (overviewQuery.isError) {
    const forbidden =
      overviewQuery.error instanceof ApiClientError &&
      (overviewQuery.error.status === 401 || overviewQuery.error.status === 403);
    return (
      <div role="alert" className="mt-6 rounded-card border border-border bg-surface p-6 text-sm">
        {forbidden ? (
          <p>
            Administrator privileges are required to view operational governance metrics.{" "}
            <Link href="/dashboard" className="text-brand-primary underline">
              Return to Dashboard
            </Link>
            .
          </p>
        ) : (
          <button
            type="button"
            onClick={() => void overviewQuery.refetch()}
            className="rounded border border-text-secondary px-3 py-1.5 font-medium"
          >
            Retry Overview
          </button>
        )}
      </div>
    );
  }

  const ov = overviewQuery.data?.data;
  if (!ov) return null;

  return (
    <div className="mt-6 space-y-6 text-text-primary">
      <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-card border border-border bg-surface p-4">
          <dt className="text-xs text-text-secondary">Active Users</dt>
          <dd className="mt-1 text-2xl font-bold">{ov.active_users_count}</dd>
        </div>
        <div className="rounded-card border border-border bg-surface p-4">
          <dt className="text-xs text-text-secondary">Enabled AQI Sources</dt>
          <dd className="mt-1 text-2xl font-bold">
            {ov.enabled_data_sources_count}{" "}
            <span className="text-xs font-normal">({ov.active_aqi_provider_mode})</span>
          </dd>
        </div>
        <div className="rounded-card border border-border bg-surface p-4">
          <dt className="text-xs text-text-secondary">RAG Corpus</dt>
          <dd className="mt-1 text-2xl font-bold">
            {ov.ingested_documents_count} docs · {ov.knowledge_chunks_count} chunks
          </dd>
        </div>
        <div className="rounded-card border border-border bg-surface p-4">
          <dt className="text-xs text-text-secondary">AI Fallback Rate</dt>
          <dd className="mt-1 text-2xl font-bold">
            {(ov.ai_fallback_rate * 100).toFixed(1)}%{" "}
            <span className="text-xs font-normal">({ov.total_ai_generations} turns)</span>
          </dd>
        </div>
      </dl>

      <section className="space-y-3 rounded-card border border-border bg-surface p-6">
        <h2 className="text-base font-semibold">Runtime System Settings</h2>
        <div className="flex flex-wrap gap-2">
          <label htmlFor="admin-banner-input" className="sr-only">
            Platform advisory notice
          </label>
          <input
            id="admin-banner-input"
            value={bannerText}
            onChange={(e) => setBannerText(e.target.value)}
            placeholder="Optional platform advisory notice..."
            aria-label="Platform advisory notice"
            className="flex-1 rounded border border-text-secondary bg-surface p-2 text-sm"
          />
          <button
            type="button"
            disabled={settingMutation.isPending}
            onClick={() => settingMutation.mutate()}
            className="rounded bg-brand-primary px-4 py-2 text-xs font-semibold text-white dark:text-background"
          >
            Save Setting
          </button>
        </div>
        {settingsQuery.data?.data.length ? (
          <ul className="space-y-2 text-xs text-text-secondary">
            {settingsQuery.data.data.map((s) => (
              <li key={s.key} className="rounded border border-border p-2">
                <strong className="text-text-primary">{s.key}:</strong>{" "}
                {JSON.stringify(s.value)}
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </div>
  );
}

export function AdminUsersWorkspace() {
  const queryClient = useQueryClient();
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const usersQuery = useQuery({
    queryKey: ["admin", "users"],
    queryFn: () => adminApi.listUsers(),
    retry: false,
  });

  const updateMutation = useMutation({
    mutationFn: (vars: {
      userId: string;
      role?: AdminAssignableRole;
      is_active?: boolean;
    }) =>
      adminApi.updateUser(vars.userId, {
        role: vars.role,
        is_active: vars.is_active,
      }),
    onSuccess: async () => {
      setErrorBanner(null);
      await queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
    onError: (err) => {
      setErrorBanner(err instanceof Error ? err.message : "Failed to update user.");
    },
  });

  if (usersQuery.isLoading) {
    return (
      <div
        aria-busy="true"
        className="mt-6 h-48 animate-pulse rounded-card border border-border bg-surface p-6"
      />
    );
  }

  if (usersQuery.isError) {
    return (
      <div role="alert" className="mt-6 rounded-card border border-border bg-surface p-6 text-sm">
        Administrator privileges are required to manage user roles and status.
      </div>
    );
  }

  const users = usersQuery.data?.data ?? [];

  return (
    <div className="mt-6 space-y-4 text-text-primary">
      {errorBanner ? (
        <div role="alert" className="rounded-lg border border-red-600/80 p-3 text-xs">
          {errorBanner}
        </div>
      ) : null}

      <div className="overflow-x-auto rounded-card border border-border bg-surface p-5">
        <table className="w-full text-left text-xs">
          <caption className="sr-only">Registered platform users, roles, and account status</caption>
          <thead>
            <tr className="border-b border-border text-text-secondary">
              <th scope="col" className="py-2 pr-4">
                Display Name
              </th>
              <th scope="col" className="py-2 pr-4">
                Email
              </th>
              <th scope="col" className="py-2 pr-4">
                Role
              </th>
              <th scope="col" className="py-2 pr-4">
                Status
              </th>
              <th scope="col" className="py-2">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-border/60">
                <td className="py-2.5 pr-4 font-medium">{u.display_name}</td>
                <td className="py-2.5 pr-4">{u.email}</td>
                <td className="py-2.5 pr-4">
                  <select
                    aria-label={`Role for ${u.email}`}
                    value={u.role}
                    disabled={updateMutation.isPending}
                    onChange={(e) =>
                      updateMutation.mutate({
                        userId: u.id,
                        role: e.target.value as AdminAssignableRole,
                      })
                    }
                    className="rounded border border-text-secondary bg-surface p-1"
                  >
                    <option value="user">user</option>
                    <option value="moderator">moderator</option>
                    <option value="admin">admin</option>
                  </select>
                </td>
                <td className="py-2.5 pr-4">
                  {u.is_active ? "Active" : "Suspended"}
                </td>
                <td className="py-2.5">
                  <button
                    type="button"
                    disabled={updateMutation.isPending}
                    onClick={() =>
                      updateMutation.mutate({ userId: u.id, is_active: !u.is_active })
                    }
                    className="rounded border border-text-secondary px-2.5 py-1 font-medium"
                  >
                    {u.is_active ? "Suspend" : "Reactivate"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
