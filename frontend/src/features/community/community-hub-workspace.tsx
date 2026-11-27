"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { WorkspaceSkeleton } from "@/components/ui/workspace-state";
import {
  CommunityDetailCard,
  CommunityDirectorySidebar,
  CommunityInitiativesCard,
  ModeratorCreateGroupForm,
} from "@/features/community/community-hub-sections";
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

function resolveActiveCommunityId(
  selectedCommunityId: string | null,
  firstCommunityId: string | undefined,
): string | null {
  if (selectedCommunityId) return selectedCommunityId;
  return firstCommunityId ?? null;
}

function canModerateCommunities(role: string | undefined): boolean {
  return role === "moderator" || role === "admin";
}

function isRegisteredRole(userId: string | null | undefined, role: string | undefined): boolean {
  return Boolean(userId && role !== "guest");
}

function CommunityMainGrid({
  communities,
  activeCommunityId,
  detail,
  initiatives,
  isAuthenticated,
  publicNameConsent,
  showReportForm,
  activeInitiativeId,
  joinPending,
  leavePending,
  reportPending,
  participatePending,
  reportForm,
  participationForm,
  onSelectCommunity,
  onToggleReportForm,
  onConsentChange,
  onJoinOrUpdate,
  onLeave,
  onSubmitReport,
  onToggleInitiative,
  onSubmitParticipation,
}: {
  communities: Array<{
    id: string;
    slug: string;
    name: string;
    city: string;
    coarse_boundary_label: string;
    description: string;
    member_count: number;
    active_initiatives_count: number;
    is_current_user_member: boolean;
    current_user_public_display_consent: boolean;
    created_at: string;
  }>;
  activeCommunityId: string | null;
  detail: Parameters<typeof CommunityDetailCard>[0]["detail"] | undefined;
  initiatives: CommunityInitiative[];
  isAuthenticated: boolean;
  publicNameConsent: boolean;
  showReportForm: boolean;
  activeInitiativeId: string | null;
  joinPending: boolean;
  leavePending: boolean;
  reportPending: boolean;
  participatePending: boolean;
  reportForm: ReturnType<typeof useForm<CreateAbuseReportFormValues>>;
  participationForm: ReturnType<typeof useForm<LogCommunityParticipationFormValues>>;
  onSelectCommunity: (id: string) => void;
  onToggleReportForm: () => void;
  onConsentChange: (checked: boolean) => void;
  onJoinOrUpdate: () => void;
  onLeave: () => void;
  onSubmitReport: (vals: CreateAbuseReportFormValues) => void;
  onToggleInitiative: (id: string) => void;
  onSubmitParticipation: (vals: LogCommunityParticipationFormValues) => void;
}) {
  if (communities.length === 0) {
    return (
      <div className="rounded-card border border-border bg-surface p-6 text-sm text-text-secondary">
        No neighborhood groups have been published yet. AirWise never displays synthetic community
        groups or fabricated participation counts.
      </div>
    );
  }
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <CommunityDirectorySidebar
        communities={communities}
        activeCommunityId={activeCommunityId}
        onSelect={onSelectCommunity}
      />

      <section aria-label="Selected community dashboard" className="space-y-5 lg:col-span-2">
        {detail ? (
          <CommunityDetailCard
            detail={detail}
            isAuthenticated={isAuthenticated}
            publicNameConsent={publicNameConsent}
            showReportForm={showReportForm}
            joinPending={joinPending}
            leavePending={leavePending}
            reportPending={reportPending}
            reportForm={reportForm}
            onToggleReportForm={onToggleReportForm}
            onConsentChange={onConsentChange}
            onJoinOrUpdate={onJoinOrUpdate}
            onLeave={onLeave}
            onSubmitReport={onSubmitReport}
          />
        ) : null}

        <CommunityInitiativesCard
          initiatives={initiatives}
          isCurrentMember={Boolean(detail?.is_current_user_member)}
          activeInitiativeId={activeInitiativeId}
          participationForm={participationForm}
          participatePending={participatePending}
          onToggleInitiative={onToggleInitiative}
          onSubmitParticipation={onSubmitParticipation}
        />
      </section>
    </div>
  );
}

function useCommunitySelectionQueries(selectedCommunityId: string | null) {
  const principalQuery = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => identityApi.getMePrincipal(),
  });
  const communitiesQuery = useQuery({
    queryKey: ["communities", "list"],
    queryFn: () => alertsCommunityApi.listCommunities(),
  });
  const communities = communitiesQuery.data ? communitiesQuery.data.data : [];
  const activeCommunityId = resolveActiveCommunityId(
    selectedCommunityId,
    communities[0]?.id,
  );
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
  const principal = principalQuery.data ? principalQuery.data.data : undefined;
  return {
    isLoading: communitiesQuery.isLoading,
    communities,
    activeCommunityId,
    detail: detailQuery.data ? detailQuery.data.data : undefined,
    initiatives: initiativesQuery.data ? initiativesQuery.data.data : [],
    isAuthenticated: isRegisteredRole(principal?.user_id, principal?.role),
    isModeratorOrAdmin: canModerateCommunities(principal?.role),
  };
}

export function CommunityHubWorkspace() {
  const queryClient = useQueryClient();
  const [selectedCommunityId, setSelectedCommunityId] = useState<string | null>(null);
  const [publicNameConsent, setPublicNameConsent] = useState(false);
  const [activeInitiativeId, setActiveInitiativeId] = useState<string | null>(null);
  const [showReportForm, setShowReportForm] = useState(false);
  const [banner, setBanner] = useState<string | null>(null);

  const hub = useCommunitySelectionQueries(selectedCommunityId);
  const activeCommunityId = hub.activeCommunityId;

  useEffect(() => {
    if (hub.detail) {
      setPublicNameConsent(hub.detail.current_user_public_display_consent);
    }
  }, [hub.detail]);

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

  if (hub.isLoading) {
    return <WorkspaceSkeleton className="mt-6 h-56" />;
  }

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

      {hub.isModeratorOrAdmin ? (
        <ModeratorCreateGroupForm
          form={createGroupForm}
          isPending={createGroupMutation.isPending}
          onSubmit={(vals) => createGroupMutation.mutate(vals)}
        />
      ) : null}

      <CommunityMainGrid
        communities={hub.communities}
        activeCommunityId={activeCommunityId}
        detail={hub.detail}
        initiatives={hub.initiatives}
        isAuthenticated={hub.isAuthenticated}
        publicNameConsent={publicNameConsent}
        showReportForm={showReportForm}
        activeInitiativeId={activeInitiativeId}
        joinPending={joinMutation.isPending}
        leavePending={leaveMutation.isPending}
        reportPending={reportMutation.isPending}
        participatePending={participateMutation.isPending}
        reportForm={reportForm}
        participationForm={participationForm}
        onSelectCommunity={setSelectedCommunityId}
        onToggleReportForm={() => setShowReportForm((prev) => !prev)}
        onConsentChange={setPublicNameConsent}
        onJoinOrUpdate={() => joinMutation.mutate()}
        onLeave={() => leaveMutation.mutate()}
        onSubmitReport={(vals) => reportMutation.mutate(vals)}
        onToggleInitiative={(id) =>
          setActiveInitiativeId((prev) => (prev === id ? null : id))
        }
        onSubmitParticipation={(vals) => participateMutation.mutate(vals)}
      />
    </div>
  );
}
