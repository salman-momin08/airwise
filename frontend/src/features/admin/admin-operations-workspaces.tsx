"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { trustedCitationUrl } from "@/components/assistant/guidance-card";
import { adminApi } from "@/lib/api/admin";

export function AdminDataSourcesWorkspace() {
  const queryClient = useQueryClient();

  const sourcesQuery = useQuery({
    queryKey: ["admin", "data-sources"],
    queryFn: () => adminApi.listDataSources(),
    retry: false,
  });

  const seedMutation = useMutation({
    mutationFn: () => adminApi.seedDefaultDataSources(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin", "data-sources"] });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: (vars: { id: string; is_enabled: boolean }) =>
      adminApi.updateDataSource(vars.id, { is_enabled: vars.is_enabled }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin", "data-sources"] });
    },
  });

  if (sourcesQuery.isLoading) {
    return (
      <div
        aria-busy="true"
        className="mt-6 h-40 animate-pulse rounded-card border border-border bg-surface p-6"
      />
    );
  }

  if (sourcesQuery.isError) {
    return (
      <div role="alert" className="mt-6 rounded-card border border-border bg-surface p-6 text-sm">
        Administrator privileges are required to manage environmental data sources.
      </div>
    );
  }

  const sources = sourcesQuery.data?.data ?? [];

  return (
    <div className="mt-6 space-y-4 text-text-primary">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-border bg-surface p-4">
        <p className="text-xs text-text-secondary">
          Configure provider priority rank, refresh cadence, and failover eligibility.
        </p>
        <button
          type="button"
          disabled={seedMutation.isPending}
          onClick={() => seedMutation.mutate()}
          className="rounded bg-brand-primary px-3 py-1.5 text-xs font-semibold text-white dark:text-background"
        >
          {seedMutation.isPending ? "Seeding..." : "Register Default Provider Catalog"}
        </button>
      </div>

      {sources.length === 0 ? (
        <p className="rounded-card border border-border bg-surface p-6 text-sm text-text-secondary">
          No air quality sources registered in database yet. Click{" "}
          <strong>Register Default Provider Catalog</strong> to initialize OpenAQ, OpenWeather, and
          CPCB entries.
        </p>
      ) : (
        <ul className="space-y-3">
          {sources.map((src) => (
            <li
              key={src.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-border bg-surface p-5 text-sm"
            >
              <div>
                <p className="font-semibold">
                  {src.name} <span className="text-xs text-text-secondary">({src.slug})</span>
                </p>
                <p className="text-xs text-text-secondary">
                  Provider: {src.provider_type} · Priority Rank: {src.priority_rank} · Refresh:{" "}
                  {src.refresh_interval_seconds}s
                </p>
              </div>
              <button
                type="button"
                disabled={toggleMutation.isPending}
                onClick={() =>
                  toggleMutation.mutate({ id: src.id, is_enabled: !src.is_enabled })
                }
                className="rounded border border-text-secondary px-3 py-1.5 text-xs font-semibold"
              >
                {src.is_enabled ? "Enabled (Disable)" : "Disabled (Enable)"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function AdminKnowledgeWorkspace() {
  const kbQuery = useQuery({
    queryKey: ["admin", "knowledge-base"],
    queryFn: () => adminApi.getKnowledgeGovernance(),
    retry: false,
  });

  if (kbQuery.isLoading) {
    return (
      <div
        aria-busy="true"
        className="mt-6 h-48 animate-pulse rounded-card border border-border bg-surface p-6"
      />
    );
  }

  if (kbQuery.isError) {
    return (
      <div role="alert" className="mt-6 rounded-card border border-border bg-surface p-6 text-sm">
        Administrator privileges are required to inspect RAG corpus governance.
      </div>
    );
  }

  const data = kbQuery.data?.data;
  const docs = data?.documents ?? [];
  const jobs = data?.recent_jobs ?? [];

  return (
    <div className="mt-6 space-y-6 text-text-primary">
      <section className="space-y-3 rounded-card border border-border bg-surface p-6">
        <h2 className="text-base font-semibold">
          Ingested Tier-1 Official Guidance Documents ({docs.length})
        </h2>
        {docs.length === 0 ? (
          <p className="text-sm text-text-secondary">
            No documents ingested yet. Run <code>python -m scripts.ingest_knowledge</code> from{" "}
            <code>backend/</code> with <code>GEMINI_API_KEY</code> configured.
          </p>
        ) : (
          <ul className="space-y-3 text-sm">
            {docs.map((doc) => {
              const safeUrl = trustedCitationUrl(doc.source_url);
              return (
                <li key={doc.id} className="rounded-lg border border-border p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-semibold">{doc.title}</p>
                    <span className="text-xs text-text-secondary">
                      {doc.chunks_count} chunk(s) · {doc.jurisdiction}
                    </span>
                  </div>
                  <p className="text-xs text-text-secondary">
                    Publisher: {doc.publisher} · Last reviewed:{" "}
                    {new Date(doc.last_reviewed_date).toLocaleDateString()}
                    {doc.is_review_overdue ? " (Review Overdue)" : ""}
                  </p>
                  {safeUrl ? (
                    <a
                      href={safeUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-1 inline-block text-xs text-brand-primary underline"
                    >
                      Inspect Official Source
                    </a>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="space-y-3 rounded-card border border-border bg-surface p-6">
        <h2 className="text-base font-semibold">Recent Ingestion Jobs ({jobs.length})</h2>
        {jobs.length === 0 ? (
          <p className="text-sm text-text-secondary">No ingestion jobs recorded yet.</p>
        ) : (
          <ul className="space-y-2 text-xs">
            {jobs.map((j) => (
              <li
                key={j.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded border border-border p-3"
              >
                <span className="truncate font-medium">{j.source_url}</span>
                <span>
                  Status: <strong>{j.status}</strong>
                  {j.error_code ? ` (${j.error_code})` : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

export function AdminAIMonitoringWorkspace() {
  const aiQuery = useQuery({
    queryKey: ["admin", "ai-monitoring"],
    queryFn: () => adminApi.getAIMonitoring(),
    retry: false,
  });

  if (aiQuery.isLoading) {
    return (
      <div
        aria-busy="true"
        className="mt-6 h-48 animate-pulse rounded-card border border-border bg-surface p-6"
      />
    );
  }

  if (aiQuery.isError) {
    return (
      <div role="alert" className="mt-6 rounded-card border border-border bg-surface p-6 text-sm">
        Administrator privileges are required to view AI telemetry and latency metrics.
      </div>
    );
  }

  const m = aiQuery.data?.data;
  if (!m) return null;

  return (
    <div className="mt-6 space-y-6 text-text-primary">
      <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-card border border-border bg-surface p-4">
          <dt className="text-xs text-text-secondary">Recorded AI Turns</dt>
          <dd className="mt-1 text-2xl font-bold">{m.total_generations}</dd>
        </div>
        <div className="rounded-card border border-border bg-surface p-4">
          <dt className="text-xs text-text-secondary">Safe Fallback Rate</dt>
          <dd className="mt-1 text-2xl font-bold">{(m.fallback_rate * 100).toFixed(1)}%</dd>
        </div>
        <div className="rounded-card border border-border bg-surface p-4">
          <dt className="text-xs text-text-secondary">AI Latency (Avg / p95)</dt>
          <dd className="mt-1 text-xl font-bold">
            {m.avg_latency_ms}ms / {m.p95_latency_ms}ms
          </dd>
        </div>
        <div className="rounded-card border border-border bg-surface p-4">
          <dt className="text-xs text-text-secondary">HTTP p95 &amp; Cache Hits</dt>
          <dd className="mt-1 text-xl font-bold">
            {m.runtime_http_p95_ms}ms · {m.runtime_aqi_cache_hits} hits
          </dd>
        </div>
      </dl>

      <div className="grid gap-4 sm:grid-cols-2">
        <section className="rounded-card border border-border bg-surface p-5 text-xs">
          <h2 className="text-sm font-semibold">Allowlisted Tool Invocations</h2>
          {Object.keys(m.tool_invocations).length === 0 ? (
            <p className="mt-2 text-text-secondary">No tool invocations recorded yet.</p>
          ) : (
            <ul className="mt-2 space-y-1">
              {Object.entries(m.tool_invocations).map(([tool, count]) => (
                <li key={tool} className="flex justify-between">
                  <span>{tool}</span>
                  <strong>{count}</strong>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-card border border-border bg-surface p-5 text-xs">
          <h2 className="text-sm font-semibold">Deterministic Fallback Reasons</h2>
          {Object.keys(m.fallback_reasons).length === 0 ? (
            <p className="mt-2 text-text-secondary">No fallback activations recorded yet.</p>
          ) : (
            <ul className="mt-2 space-y-1">
              {Object.entries(m.fallback_reasons).map(([reason, count]) => (
                <li key={reason} className="flex justify-between">
                  <span>{reason}</span>
                  <strong>{count}</strong>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

export function AdminAuditLogsWorkspace() {
  const [prefix, setPrefix] = useState("");

  const logsQuery = useQuery({
    queryKey: ["admin", "audit-logs", prefix],
    queryFn: () => adminApi.listAuditLogs(prefix.trim() || undefined),
    retry: false,
  });

  if (logsQuery.isLoading) {
    return (
      <div
        aria-busy="true"
        className="mt-6 h-48 animate-pulse rounded-card border border-border bg-surface p-6"
      />
    );
  }

  if (logsQuery.isError) {
    return (
      <div role="alert" className="mt-6 rounded-card border border-border bg-surface p-6 text-sm">
        Administrator privileges are required to inspect security audit logs.
      </div>
    );
  }

  const logs = logsQuery.data?.data ?? [];

  return (
    <div className="mt-6 space-y-4 text-text-primary">
      <div className="rounded-card border border-border bg-surface p-4">
        <label className="text-xs font-medium">
          Filter by Action Prefix (e.g., <code>admin.</code>, <code>community.</code>,{" "}
          <code>user.</code>)
          <input
            value={prefix}
            onChange={(e) => setPrefix(e.target.value)}
            className="ml-2 rounded border border-text-secondary bg-surface p-1.5 text-xs"
          />
        </label>
      </div>

      <div className="overflow-x-auto rounded-card border border-border bg-surface p-5">
        {logs.length === 0 ? (
          <p className="text-sm text-text-secondary">No matching audit log events.</p>
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-border text-text-secondary">
                <th className="py-2 pr-4">Timestamp</th>
                <th className="py-2 pr-4">Action</th>
                <th className="py-2 pr-4">Target</th>
                <th className="py-2 pr-4">Actor ID</th>
                <th className="py-2">Redacted Metadata</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((item) => (
                <tr key={item.id} className="border-b border-border/60">
                  <td className="py-2 pr-4">
                    {new Date(item.created_at).toLocaleString()}
                  </td>
                  <td className="py-2 pr-4 font-semibold">{item.action}</td>
                  <td className="py-2 pr-4">
                    {item.target_type}
                    {item.target_id ? `:${item.target_id}` : ""}
                  </td>
                  <td className="py-2 pr-4 text-text-secondary">
                    {item.actor_user_id ?? "anonymized/system"}
                  </td>
                  <td className="py-2 font-mono text-[11px] text-text-secondary">
                    {JSON.stringify(item.metadata_redacted)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
