"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { alertsCommunityApi } from "@/lib/api/alerts-community";
import { identityApi } from "@/lib/api/identity";
import {
  createAbuseReportFormSchema,
  createCommunityFormSchema,
  logCommunityParticipationFormSchema,
  type CreateAbuseReportFormValues,
  type CreateCommunityFormValues,
  type LogCommunityParticipationFormValues,
} from "@/lib/validation/alerts-community";
import type { CommunityInitiative } from "@/types/alerts-community";

export function CommunityHubWorkspace() {
  const queryClient = useQueryClient();
  const [selectedCommunityId, setSelectedCommunityId] = useState<string | null>(null);
  const [publicNameConsent, setPublicNameConsent] = useState(false);
  const [activeInitiativeId, setActiveInitiativeId] = useState<string | null>(null);
  const [showReportForm, setShowReportForm] = useState(false);
  const [banner, setBanner] = useState<string | null>(null);

  const principalQuery = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => identityApi.getMePrincipal(),
  });

  const communitiesQuery = useQuery({
    queryKey: ["communities", "list"],
    queryFn: () => alertsCommunityApi.listCommunities(),
  });

  const communities = communitiesQuery.data?.data ?? [];
  const activeCommunityId = selectedCommunityId ?? communities[0]?.id ?? null;

  const detailQuery = useQuery({
    queryKey: ["communities", "detail", activeCommunityId],
    queryFn: () => {
      if (!activeCommunityId) throw new Error("No community selected.");
      return alertsCommunityApi.getCommunityDetail(activeCommunityId);
    },
    enabled: activeCommunityId !== null,
  });

  const initiativesQuery = useQuery({
    queryKey: ["communities", "initiatives", activeCommunityId],
    queryFn: () => {
      if (!activeCommunityId) throw new Error("No community selected.");
      return alertsCommunityApi.listInitiatives(activeCommunityId);
    },
    enabled: activeCommunityId !== null,
  });

  useEffect(() => {
    if (detailQuery.data?.data) {
      setPublicNameConsent(detailQuery.data.data.current_user_public_display_consent);
    }
  }, [detailQuery.data]);

  const participationForm = useForm<LogCommunityParticipationFormValues>({
    resolver: zodResolver(logCommunityParticipationFormSchema),
    defaultValues: {
      self_reported_actions_count: 1,
      commute_distance_saved_km: 8,
      note: "",
    },
  });

  const reportForm = useForm<CreateAbuseReportFormValues>({
    resolver: zodResolver(createAbuseReportFormSchema),
    defaultValues: {
      reason_category: "misinformation",
      details: "",
    },
  });

  const createGroupForm = useForm<CreateCommunityFormValues>({
    resolver: zodResolver(createCommunityFormSchema),
    defaultValues: {
      slug: "",
      name: "",
      city: "Delhi",
      coarse_boundary_label: "",
      description: "",
    },
  });

  const joinMutation = useMutation({
    mutationFn: () => {
      if (!activeCommunityId) throw new Error("Select a community first.");
      return alertsCommunityApi.joinCommunity(activeCommunityId, publicNameConsent);
    },
    onSuccess: async () => {
      setBanner("Membership & privacy display consent updated.");
      await queryClient.invalidateQueries({ queryKey: ["communities"] });
    },
  });

  const leaveMutation = useMutation({
    mutationFn: () => {
      if (!activeCommunityId) throw new Error("Select a community first.");
      return alertsCommunityApi.leaveCommunity(activeCommunityId);
    },
    onSuccess: async () => {
      setBanner("You have left this neighborhood group.");
      await queryClient.invalidateQueries({ queryKey: ["communities"] });
    },
  });

  const participateMutation = useMutation({
    mutationFn: (values: LogCommunityParticipationFormValues) => {
      if (!activeCommunityId || !activeInitiativeId) {
        throw new Error("Select an initiative first.");
      }
      return alertsCommunityApi.logParticipation(
        activeCommunityId,
        activeInitiativeId,
        values,
      );
    },
    onSuccess: async () => {
      setBanner(
        "Voluntary action logged! Aggregate self-reported totals have been updated.",
      );
      setActiveInitiativeId(null);
      participationForm.reset();
      await queryClient.invalidateQueries({ queryKey: ["communities"] });
    },
  });

  const reportMutation = useMutation({
    mutationFn: (values: CreateAbuseReportFormValues) => {
      if (!activeCommunityId) throw new Error("Select a community first.");
      return alertsCommunityApi.submitAbuseReport(activeCommunityId, values);
    },
    onSuccess: () => {
      setBanner("Report submitted to the community moderation queue.");
      setShowReportForm(false);
      reportForm.reset();
    },
  });

  const createGroupMutation = useMutation({
    mutationFn: (values: CreateCommunityFormValues) =>
      alertsCommunityApi.createCommunity(values),
    onSuccess: async (res) => {
      setSelectedCommunityId(res.data.id);
      setBanner(`Neighborhood group '${res.data.name}' created.`);
      createGroupForm.reset();
      await queryClient.invalidateQueries({ queryKey: ["communities"] });
    },
  });

  if (communitiesQuery.isLoading) {
    return (
      <div
        aria-busy="true"
        className="mt-6 h-56 animate-pulse rounded-card border border-border bg-surface p-6"
      />
    );
  }

  const principal = principalQuery.data?.data;
  const isAuthenticated = Boolean(principal?.user_id && principal.role !== "guest");
  const isModeratorOrAdmin =
    principal?.role === "moderator" || principal?.role === "admin";
  const detail = detailQuery.data?.data;
  const initiatives: CommunityInitiative[] = initiativesQuery.data?.data ?? [];

  return (
    <div className="mt-6 space-y-6 text-text-primary">
      <div
        role="note"
        className="rounded-card border border-border bg-surface p-5 text-xs text-text-secondary"
      >
        <strong className="text-text-primary">Privacy &amp; Scientific Honesty Guardrail:</strong>{" "}
        Communities use coarse neighborhood labels only—exact street addresses and household GPS
        coordinates are strictly prohibited. Member display names are hidden unless you explicitly
        opt in, and challenge totals represent voluntary self-reported CO₂e estimates rather than
        measured ambient AQI reductions.
      </div>

      {banner ? (
        <div
          role="status"
          className="rounded-lg border border-brand-primary/60 bg-brand-accent/40 px-4 py-3 text-sm font-medium"
        >
          {banner}
        </div>
      ) : null}

      {isModeratorOrAdmin ? (
        <form
          onSubmit={createGroupForm.handleSubmit((vals) => createGroupMutation.mutate(vals))}
          className="space-y-4 rounded-card border border-border bg-surface p-6"
        >
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold">
              Moderator · Create Coarse-Boundary Neighborhood Group
            </h2>
            <Link href="/admin/community" className="text-xs text-brand-primary underline">
              Open Moderation Queue
            </Link>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-xs font-medium">
              Group Name
              <input
                {...createGroupForm.register("name")}
                placeholder="Indiranagar Clean Commute Circle"
                className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
              />
            </label>
            <label className="text-xs font-medium">
              Slug
              <input
                {...createGroupForm.register("slug")}
                placeholder="indiranagar-clean-commute"
                className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
              />
            </label>
            <label className="text-xs font-medium">
              City
              <input
                {...createGroupForm.register("city")}
                className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
              />
            </label>
            <label className="text-xs font-medium">
              Coarse Boundary Label (No street numbers/GPS)
              <input
                {...createGroupForm.register("coarse_boundary_label")}
                placeholder="East Bengaluru · Metro Corridor"
                className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
              />
            </label>
            <label className="text-xs font-medium sm:col-span-2">
              Description
              <textarea
                rows={2}
                {...createGroupForm.register("description")}
                placeholder="Voluntary carpool, transit, and school no-idling initiatives."
                className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
              />
            </label>
          </div>
          <button
            type="submit"
            disabled={createGroupMutation.isPending}
            className="rounded bg-brand-primary px-4 py-2 text-xs font-semibold text-white dark:text-background"
          >
            Create Neighborhood Group
          </button>
        </form>
      ) : null}

      {communities.length === 0 ? (
        <div className="rounded-card border border-border bg-surface p-6 text-sm text-text-secondary">
          No neighborhood groups have been published yet. AirWise never displays synthetic
          community groups or fabricated participation counts.
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-3">
          <section aria-label="Discover neighborhood groups" className="space-y-3">
            <h2 className="text-base font-semibold">Neighborhood Groups</h2>
            {communities.map((comm) => (
              <button
                key={comm.id}
                type="button"
                onClick={() => setSelectedCommunityId(comm.id)}
                className={`w-full rounded-card border p-4 text-left transition-colors ${
                  comm.id === activeCommunityId
                    ? "border-brand-primary bg-surface shadow-sm"
                    : "border-border bg-surface"
                }`}
              >
                <p className="font-semibold text-text-primary">{comm.name}</p>
                <p className="text-xs text-text-secondary">
                  {comm.city} · {comm.coarse_boundary_label}
                </p>
                <p className="mt-2 text-xs text-text-secondary">
                  {comm.member_count} member(s) · {comm.active_initiatives_count} active
                  initiative(s)
                </p>
              </button>
            ))}
          </section>

          <section
            aria-label="Selected community dashboard"
            className="space-y-5 lg:col-span-2"
          >
            {detail ? (
              <div className="space-y-4 rounded-card border border-border bg-surface p-6">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-bold">{detail.name}</h2>
                    <p className="text-xs text-text-secondary">
                      {detail.city} · Coarse Area: <strong>{detail.coarse_boundary_label}</strong>
                    </p>
                  </div>
                  {isAuthenticated ? (
                    <button
                      type="button"
                      onClick={() => setShowReportForm((prev) => !prev)}
                      className="rounded border border-text-secondary px-3 py-1 text-xs"
                    >
                      Report Issue / PII
                    </button>
                  ) : null}
                </div>

                <p className="text-sm text-text-secondary">{detail.description}</p>

                <dl className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-lg border border-border p-3">
                    <dt className="text-xs text-text-secondary">Members</dt>
                    <dd className="mt-1 text-xl font-bold">{detail.member_count}</dd>
                  </div>
                  <div className="rounded-lg border border-border p-3">
                    <dt className="text-xs text-text-secondary">Self-Reported Actions</dt>
                    <dd className="mt-1 text-xl font-bold">
                      {detail.total_self_reported_actions}
                    </dd>
                  </div>
                  <div className="rounded-lg border border-brand-primary/50 bg-brand-accent/30 p-3">
                    <dt className="text-xs text-text-secondary">Est. Avoided CO₂e</dt>
                    <dd className="mt-1 text-xl font-bold">
                      {detail.total_estimated_avoided_co2e_kg}{" "}
                      <span className="text-xs font-normal">kg</span>
                    </dd>
                  </div>
                </dl>

                {detail.consented_member_display_names.length > 0 ? (
                  <p className="text-xs text-text-secondary">
                    <strong className="text-text-primary">
                      Opt-In Public Contributors:
                    </strong>{" "}
                    {detail.consented_member_display_names.join(", ")}
                  </p>
                ) : (
                  <p className="text-xs text-text-secondary">
                    Individual member names are private by default (0 members opted into public
                    display).
                  </p>
                )}

                {isAuthenticated ? (
                  <div className="space-y-3 border-t border-border pt-4">
                    <label className="flex items-center gap-2 text-xs">
                      <input
                        type="checkbox"
                        checked={publicNameConsent}
                        onChange={(e) => setPublicNameConsent(e.target.checked)}
                      />
                      Optional: Show my display name in this group&apos;s public contributor list
                      (off by default)
                    </label>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        disabled={joinMutation.isPending}
                        onClick={() => joinMutation.mutate()}
                        className="rounded bg-brand-primary px-4 py-1.5 text-xs font-semibold text-white dark:text-background"
                      >
                        {detail.is_current_user_member
                          ? "Update Privacy Consent"
                          : "Join Neighborhood Group"}
                      </button>
                      {detail.is_current_user_member ? (
                        <button
                          type="button"
                          disabled={leaveMutation.isPending}
                          onClick={() => leaveMutation.mutate()}
                          className="rounded border border-text-secondary px-3 py-1.5 text-xs"
                        >
                          Leave Group
                        </button>
                      ) : null}
                    </div>
                  </div>
                ) : (
                  <p className="border-t border-border pt-3 text-xs text-text-secondary">
                    <Link href="/login" className="font-semibold text-brand-primary underline">
                      Sign in
                    </Link>{" "}
                    to join this group or log voluntary clean-air challenge actions.
                  </p>
                )}

                {showReportForm ? (
                  <form
                    onSubmit={reportForm.handleSubmit((vals) => reportMutation.mutate(vals))}
                    className="space-y-3 rounded-lg border border-border bg-background p-4"
                  >
                    <h3 className="text-sm font-semibold">Report Moderation or Privacy Concern</h3>
                    <select
                      {...reportForm.register("reason_category")}
                      className="w-full rounded border border-text-secondary bg-surface p-2 text-xs"
                    >
                      <option value="pii_exposure">Personal / Exact Location Exposure</option>
                      <option value="misinformation">Scientific / AQI Misinformation</option>
                      <option value="unsafe_health_advice">Unsafe Health Advice</option>
                      <option value="harassment_or_spam">Harassment or Spam</option>
                    </select>
                    <textarea
                      rows={2}
                      {...reportForm.register("details")}
                      placeholder="Describe the concern for moderator review..."
                      className="w-full rounded border border-text-secondary bg-surface p-2 text-xs"
                    />
                    <button
                      type="submit"
                      disabled={reportMutation.isPending}
                      className="rounded bg-brand-primary px-3 py-1.5 text-xs font-semibold text-white dark:text-background"
                    >
                      Submit Report
                    </button>
                  </form>
                ) : null}
              </div>
            ) : null}

            <div className="space-y-3 rounded-card border border-border bg-surface p-6">
              <h3 className="text-base font-semibold">Active Clean-Air Initiatives</h3>
              {initiatives.length === 0 ? (
                <p className="text-sm text-text-secondary">
                  No active challenges in this neighborhood right now.
                </p>
              ) : (
                <ul className="space-y-4">
                  {initiatives.map((init) => (
                    <li key={init.id} className="space-y-2 rounded-lg border border-border p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <h4 className="font-semibold">{init.title}</h4>
                        <span className="rounded-full border border-border px-2.5 py-0.5 text-xs text-text-secondary">
                          {init.challenge_type.replaceAll("_", " ")}
                        </span>
                      </div>
                      <p className="text-xs text-text-secondary">{init.description}</p>
                      <p className="text-xs font-medium text-text-primary">
                        Self-reported aggregate: {init.total_self_reported_actions} action(s) · Est.{" "}
                        {init.total_estimated_avoided_co2e_kg} kg CO₂e avoided
                      </p>
                      {detail?.is_current_user_member ? (
                        <button
                          type="button"
                          onClick={() =>
                            setActiveInitiativeId((prev) => (prev === init.id ? null : init.id))
                          }
                          className="rounded border border-text-secondary px-3 py-1 text-xs font-semibold"
                        >
                          Log Voluntary Action
                        </button>
                      ) : null}

                      {activeInitiativeId === init.id ? (
                        <form
                          onSubmit={participationForm.handleSubmit((vals) =>
                            participateMutation.mutate(vals),
                          )}
                          className="mt-2 space-y-3 rounded border border-border bg-background p-3 text-xs"
                        >
                          <div className="grid gap-3 sm:grid-cols-2">
                            <label>
                              Completed Actions Count
                              <input
                                type="number"
                                {...participationForm.register("self_reported_actions_count")}
                                className="mt-1 w-full rounded border border-text-secondary bg-surface p-1.5"
                              />
                            </label>
                            <label>
                              Optional Solo-Car Distance Replaced (km)
                              <input
                                type="number"
                                step="0.5"
                                {...participationForm.register("commute_distance_saved_km")}
                                className="mt-1 w-full rounded border border-text-secondary bg-surface p-1.5"
                              />
                            </label>
                          </div>
                          <label className="block">
                            Optional Note (No street addresses or emails)
                            <input
                              {...participationForm.register("note")}
                              className="mt-1 w-full rounded border border-text-secondary bg-surface p-1.5"
                            />
                          </label>
                          {participationForm.formState.errors.note ? (
                            <p className="text-red-700 dark:text-red-300">
                              {participationForm.formState.errors.note.message}
                            </p>
                          ) : null}
                          <button
                            type="submit"
                            disabled={participateMutation.isPending}
                            className="rounded bg-brand-primary px-3 py-1.5 font-semibold text-white dark:text-background"
                          >
                            Submit Self-Reported Entry
                          </button>
                        </form>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
