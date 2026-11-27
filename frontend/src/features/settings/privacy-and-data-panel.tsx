"use client";

/**
 * Self-service GDPR JSON account export, chat history controls, and right-to-erasure panel.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiClientError } from "@/lib/api/client";
import { identityApi } from "@/lib/api/identity";

export function PrivacyAndDataPanel() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [confirmDeleteText, setConfirmDeleteText] = useState("");
  const [exportStatus, setExportStatus] = useState<string | null>(null);

  const meQuery = useQuery({
    queryKey: ["users", "me"],
    queryFn: () => identityApi.getUserProfileAndPreferences(),
  });

  const toggleChatRetentionMutation = useMutation({
    mutationFn: (saveChatHistory: boolean) =>
      identityApi.updatePreferences({ save_chat_history: saveChatHistory }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["users", "me"] });
    },
  });

  const exportMutation = useMutation({
    mutationFn: () => identityApi.exportAccountData(),
    onSuccess: (res) => {
      const jsonBlob = new Blob([JSON.stringify(res.data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(jsonBlob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `airwise-account-export-${new Date().toISOString().slice(0, 10)}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
      setExportStatus("Your portable JSON data archive has been downloaded.");
    },
  });

  const deleteAccountMutation = useMutation({
    mutationFn: () => identityApi.deleteAccount(),
    onSuccess: () => {
      queryClient.clear();
      router.push("/");
    },
  });

  if (meQuery.isLoading) {
    return (
      <div
        aria-busy="true"
        className="h-48 animate-pulse rounded-card border border-border bg-surface p-6"
      />
    );
  }

  if (meQuery.isError) {
    const unauth = meQuery.error instanceof ApiClientError && meQuery.error.status === 401;
    return (
      <div role="alert" className="rounded-card border border-border bg-surface p-6 text-sm">
        {unauth ? (
          <p>
            Please{" "}
            <Link href="/login" className="font-semibold text-brand-primary underline">
              sign in
            </Link>{" "}
            to export your account data or manage deletion settings.
          </p>
        ) : (
          <p>Unable to load privacy controls right now.</p>
        )}
      </div>
    );
  }

  const saveChatHistory = meQuery.data?.data.preferences.save_chat_history ?? true;

  return (
    <div className="space-y-8">
      <section className="rounded-card border border-border bg-surface p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-text-primary">
          AirWise Copilot Conversation Retention
        </h2>
        <p className="mt-1 text-xs text-text-secondary">
          Control whether AirWise Copilot persists chat history across sessions. Raw prompts are
          never written to application logs.
        </p>

        <label className="mt-4 flex items-center gap-3 text-sm font-medium text-text-primary">
          <input
            type="checkbox"
            checked={saveChatHistory}
            disabled={toggleChatRetentionMutation.isPending}
            onChange={(e) => toggleChatRetentionMutation.mutate(e.target.checked)}
            className="h-4 w-4 accent-brand-primary"
          />
          Persist my AirWise Copilot conversations in my account
        </label>
      </section>

      <section className="rounded-card border border-border bg-surface p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-text-primary">
          Portable JSON Data Export (GDPR / DPDP)
        </h2>
        <p className="mt-1 text-xs text-text-secondary">
          Download a complete machine-readable JSON copy of your profile, consented preferences,
          and saved locations.
        </p>

        {exportStatus ? (
          <p role="status" className="mt-3 text-xs font-medium text-emerald-800 dark:text-emerald-300">
            {exportStatus}
          </p>
        ) : null}

        <button
          type="button"
          onClick={() => exportMutation.mutate()}
          disabled={exportMutation.isPending}
          className="mt-4 rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-60 dark:text-background"
        >
          {exportMutation.isPending ? "Preparing JSON archive…" : "Download JSON data export"}
        </button>
      </section>

      <section className="rounded-card border border-red-400/50 bg-surface p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-red-700 dark:text-red-300">
          Permanent Account &amp; PII Deletion
        </h2>
        <p className="mt-1 text-xs text-text-secondary">
          Permanently deletes your account, profile, preferences, saved locations, and active
          sessions, and anonymizes audit log references. This action cannot be undone.
        </p>

        <div className="mt-4 max-w-sm">
          <label
            htmlFor="confirm-delete"
            className="block text-xs font-medium text-text-primary"
          >
            Type <strong>DELETE</strong> to confirm permanent erasure
          </label>
          <input
            id="confirm-delete"
            type="text"
            value={confirmDeleteText}
            onChange={(e) => setConfirmDeleteText(e.target.value)}
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary"
          />
        </div>

        <button
          type="button"
          disabled={confirmDeleteText !== "DELETE" || deleteAccountMutation.isPending}
          onClick={() => deleteAccountMutation.mutate()}
          className="mt-4 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
        >
          {deleteAccountMutation.isPending ? "Deleting account…" : "Permanently delete my account"}
        </button>
      </section>
    </div>
  );
}
