"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { WorkspaceAuthOrErrorNotice } from "@/components/ui/workspace-state";
import { identityApi } from "@/lib/api/identity";
import {
  profileSettingsSchema,
  type ProfileSettingsFormValues,
} from "@/lib/validation/identity";
import { useLocationStore } from "@/stores/location-store";
import type { SessionRecord } from "@/types/api";

function ActiveSessionsSection({
  sessions,
  isLoading,
  revokePending,
  revokeOthersPending,
  onRevokeOthers,
  onRevokeSession,
}: {
  sessions: SessionRecord[];
  isLoading: boolean;
  revokePending: boolean;
  revokeOthersPending: boolean;
  onRevokeOthers: () => void;
  onRevokeSession: (sessionId: string) => void;
}) {
  return (
    <section className="rounded-card border border-border bg-surface p-6 shadow-sm">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold text-text-primary">Active Browser Sessions</h2>
          <p className="text-xs text-text-secondary">
            HttpOnly server-tracked sessions. Revoke unfamiliar devices immediately.
          </p>
        </div>
        <button
          type="button"
          onClick={onRevokeOthers}
          disabled={revokeOthersPending}
          className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-medium text-text-primary hover:bg-brand-accent/30 disabled:opacity-60"
        >
          Sign out other devices
        </button>
      </div>

      {isLoading ? (
        <div aria-busy="true" className="h-16 animate-pulse rounded-lg bg-border" />
      ) : (
        <ul className="divide-y divide-border text-sm">
          {sessions.map((sess) => (
            <li
              key={sess.id}
              className="flex flex-wrap items-center justify-between gap-3 py-3"
            >
              <div>
                <p className="font-medium text-text-primary">
                  {sess.user_agent ?? "Browser session"}{" "}
                  {sess.is_current ? (
                    <span className="ml-2 rounded border border-brand-primary/50 bg-brand-accent px-2 py-0.5 text-xs font-semibold text-text-primary">
                      Current device
                    </span>
                  ) : null}
                </p>
                <p className="text-xs text-text-secondary">
                  Signed in {new Date(sess.created_at).toLocaleString()} · Expires{" "}
                  {new Date(sess.expires_at).toLocaleString()}
                </p>
              </div>
              {!sess.is_current ? (
                <button
                  type="button"
                  onClick={() => onRevokeSession(sess.id)}
                  disabled={revokePending}
                  className="rounded-lg border border-red-400/50 px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-500/10 dark:text-red-300"
                >
                  Revoke
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function ProfileAndSessionsPanel() {
  const queryClient = useQueryClient();
  const setAqiStandard = useLocationStore((state) => state.setAqiStandard);
  const [savedNotice, setSavedNotice] = useState<string | null>(null);

  const meQuery = useQuery({
    queryKey: ["users", "me"],
    queryFn: () => identityApi.getUserProfileAndPreferences(),
  });

  const sessionsQuery = useQuery({
    queryKey: ["auth", "sessions"],
    queryFn: () => identityApi.listSessions(),
    enabled: meQuery.isSuccess,
  });

  const form = useForm<ProfileSettingsFormValues>({
    resolver: zodResolver(profileSettingsSchema),
    defaultValues: {
      display_name: "",
      preferred_aqi_standard: "india_naqi",
      timezone: "Asia/Kolkata",
      locale: "en",
    },
  });

  useEffect(() => {
    const profile = meQuery.data?.data.profile;
    if (!profile) return;
    form.reset({
      display_name: profile.display_name,
      preferred_aqi_standard: profile.preferred_aqi_standard,
      timezone: profile.timezone,
      locale: profile.locale === "hi" ? "hi" : "en",
    });
  }, [meQuery.data, form]);

  const updateMutation = useMutation({
    mutationFn: (values: ProfileSettingsFormValues) => identityApi.updateProfile(values),
    onSuccess: async (res) => {
      setAqiStandard(res.data.profile.preferred_aqi_standard);
      setSavedNotice("Profile settings saved.");
      await queryClient.invalidateQueries({ queryKey: ["users", "me"] });
      await queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
    },
  });

  const revokeSessionMutation = useMutation({
    mutationFn: (sessionId: string) => identityApi.revokeSession(sessionId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["auth", "sessions"] });
    },
  });

  const revokeOthersMutation = useMutation({
    mutationFn: () => identityApi.revokeOtherSessions(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["auth", "sessions"] });
    },
  });

  if (meQuery.isLoading) {
    return (
      <div
        aria-busy="true"
        className="space-y-4 rounded-card border border-border bg-surface p-6"
      >
        <div className="h-6 w-48 animate-pulse rounded bg-border" />
        <div className="h-10 w-full animate-pulse rounded bg-border" />
        <div className="h-10 w-full animate-pulse rounded bg-border" />
      </div>
    );
  }

  if (meQuery.isError) {
    return (
      <WorkspaceAuthOrErrorNotice
        error={meQuery.error}
        unauthPrompt="to view and update your profile settings."
        errorMessage="Unable to load profile settings right now."
        onRetry={() => void meQuery.refetch()}
        className=""
      />
    );
  }

  const user = meQuery.data?.data;
  const displayNameError = form.formState.errors.display_name;

  return (
    <div className="space-y-8">
      <section className="rounded-card border border-border bg-surface p-6 shadow-sm">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold text-text-primary">Account Identity</h2>
            <p className="text-xs text-text-secondary">
              Signed in as <span className="font-medium text-text-primary">{user?.email}</span> ·{" "}
              {user?.is_email_verified ? "Email verified" : "Email verification pending"}
            </p>
          </div>
        </div>

        {savedNotice ? (
          <div
            role="status"
            className="mb-4 rounded-lg border border-brand-secondary/40 bg-brand-accent/40 p-3 text-sm text-text-primary"
          >
            {savedNotice}
          </div>
        ) : null}

        <form
          onSubmit={form.handleSubmit((values) => {
            setSavedNotice(null);
            updateMutation.mutate(values);
          })}
          noValidate
          className="grid gap-4 sm:grid-cols-2"
        >
          <div>
            <label
              htmlFor="profile-display-name"
              className="block text-sm font-medium text-text-primary"
            >
              Display name
            </label>
            <input
              id="profile-display-name"
              type="text"
              aria-invalid={Boolean(displayNameError)}
              {...form.register("display_name")}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary"
            />
            {displayNameError ? (
              <p className="mt-1 text-xs text-red-600">{displayNameError.message}</p>
            ) : null}
          </div>

          <div>
            <label
              htmlFor="profile-standard"
              className="block text-sm font-medium text-text-primary"
            >
              Preferred AQI standard
            </label>
            <select
              id="profile-standard"
              {...form.register("preferred_aqi_standard")}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary"
            >
              <option value="india_naqi">India NAQI (CPCB)</option>
              <option value="us_epa">US EPA AQI</option>
            </select>
          </div>

          <div>
            <label
              htmlFor="profile-timezone"
              className="block text-sm font-medium text-text-primary"
            >
              Timezone
            </label>
            <input
              id="profile-timezone"
              type="text"
              {...form.register("timezone")}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary"
            />
          </div>

          <div>
            <label htmlFor="profile-locale" className="block text-sm font-medium text-text-primary">
              Language
            </label>
            <select
              id="profile-locale"
              {...form.register("locale")}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary"
            >
              <option value="en">English</option>
              <option value="hi">Hindi (हिन्दी)</option>
            </select>
          </div>

          <div className="sm:col-span-2">
            <button
              type="submit"
              disabled={updateMutation.isPending}
              className="rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-60 dark:text-background"
            >
              {updateMutation.isPending ? "Saving…" : "Save profile changes"}
            </button>
          </div>
        </form>
      </section>

      <ActiveSessionsSection
        sessions={sessionsQuery.data?.data ?? []}
        isLoading={sessionsQuery.isLoading}
        revokePending={revokeSessionMutation.isPending}
        revokeOthersPending={revokeOthersMutation.isPending}
        onRevokeOthers={() => revokeOthersMutation.mutate()}
        onRevokeSession={(sessionId) => revokeSessionMutation.mutate(sessionId)}
      />
    </div>
  );
}
