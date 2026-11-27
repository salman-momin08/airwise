/**
 * Consent-gated neighborhood community summary, initiatives, and abuse-reporting sections.
 */

import Link from "next/link";
import type { UseFormReturn } from "react-hook-form";
import type {
  CreateAbuseReportFormValues,
  CreateCommunityFormValues,
  LogCommunityParticipationFormValues,
} from "@/lib/validation/alerts-community";
import type {
  CommunityDetail,
  CommunityInitiative,
  CommunitySummary,
} from "@/types/alerts-community";

export function ModeratorCreateGroupForm({
  form,
  isPending,
  onSubmit,
}: {
  form: UseFormReturn<CreateCommunityFormValues>;
  isPending: boolean;
  onSubmit: (values: CreateCommunityFormValues) => void;
}) {
  return (
    <form
      onSubmit={form.handleSubmit(onSubmit)}
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
            {...form.register("name")}
            placeholder="Indiranagar Clean Commute Circle"
            className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
          />
        </label>
        <label className="text-xs font-medium">
          Slug
          <input
            {...form.register("slug")}
            placeholder="indiranagar-clean-commute"
            className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
          />
        </label>
        <label className="text-xs font-medium">
          City
          <input
            {...form.register("city")}
            className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
          />
        </label>
        <label className="text-xs font-medium">
          Coarse Boundary Label (No street numbers/GPS)
          <input
            {...form.register("coarse_boundary_label")}
            placeholder="East Bengaluru · Metro Corridor"
            className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
          />
        </label>
        <label className="text-xs font-medium sm:col-span-2">
          Description
          <textarea
            rows={2}
            {...form.register("description")}
            placeholder="Voluntary carpool, transit, and school no-idling initiatives."
            className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
          />
        </label>
      </div>
      <button
        type="submit"
        disabled={isPending}
        className="rounded bg-brand-primary px-4 py-2 text-xs font-semibold text-white dark:text-background"
      >
        Create Neighborhood Group
      </button>
    </form>
  );
}

export function CommunityDirectorySidebar({
  communities,
  activeCommunityId,
  onSelect,
}: {
  communities: CommunitySummary[];
  activeCommunityId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <section aria-label="Discover neighborhood groups" className="space-y-3">
      <h2 className="text-base font-semibold">Neighborhood Groups</h2>
      {communities.map((comm) => (
        <button
          key={comm.id}
          type="button"
          onClick={() => onSelect(comm.id)}
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
            {comm.member_count} member(s) · {comm.active_initiatives_count} active initiative(s)
          </p>
        </button>
      ))}
    </section>
  );
}

export function CommunityDetailCard({
  detail,
  isAuthenticated,
  publicNameConsent,
  showReportForm,
  joinPending,
  leavePending,
  reportPending,
  reportForm,
  onToggleReportForm,
  onConsentChange,
  onJoinOrUpdate,
  onLeave,
  onSubmitReport,
}: {
  detail: CommunityDetail;
  isAuthenticated: boolean;
  publicNameConsent: boolean;
  showReportForm: boolean;
  joinPending: boolean;
  leavePending: boolean;
  reportPending: boolean;
  reportForm: UseFormReturn<CreateAbuseReportFormValues>;
  onToggleReportForm: () => void;
  onConsentChange: (checked: boolean) => void;
  onJoinOrUpdate: () => void;
  onLeave: () => void;
  onSubmitReport: (values: CreateAbuseReportFormValues) => void;
}) {
  return (
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
            onClick={onToggleReportForm}
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
          <dd className="mt-1 text-xl font-bold">{detail.total_self_reported_actions}</dd>
        </div>
        <div className="rounded-lg border border-brand-primary/50 bg-brand-accent/30 p-3">
          <dt className="text-xs text-text-secondary">Est. Avoided CO₂e</dt>
          <dd className="mt-1 text-xl font-bold">
            {detail.total_estimated_avoided_co2e_kg} <span className="text-xs font-normal">kg</span>
          </dd>
        </div>
      </dl>

      {detail.consented_member_display_names.length > 0 ? (
        <p className="text-xs text-text-secondary">
          <strong className="text-text-primary">Opt-In Public Contributors:</strong>{" "}
          {detail.consented_member_display_names.join(", ")}
        </p>
      ) : (
        <p className="text-xs text-text-secondary">
          Individual member names are private by default (0 members opted into public display).
        </p>
      )}

      {isAuthenticated ? (
        <div className="space-y-3 border-t border-border pt-4">
          <label className="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={publicNameConsent}
              onChange={(e) => onConsentChange(e.target.checked)}
            />
            Optional: Show my display name in this group&apos;s public contributor list (off by
            default)
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={joinPending}
              onClick={onJoinOrUpdate}
              className="rounded bg-brand-primary px-4 py-1.5 text-xs font-semibold text-white dark:text-background"
            >
              {detail.is_current_user_member ? "Update Privacy Consent" : "Join Neighborhood Group"}
            </button>
            {detail.is_current_user_member ? (
              <button
                type="button"
                disabled={leavePending}
                onClick={onLeave}
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
          onSubmit={reportForm.handleSubmit(onSubmitReport)}
          className="space-y-3 rounded-lg border border-border bg-background p-4"
        >
          <h3 className="text-sm font-semibold">Report Moderation or Privacy Concern</h3>
          <label className="block text-xs font-medium">
            Concern Category
            <select
              {...reportForm.register("reason_category")}
              className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-xs"
            >
              <option value="pii_exposure">Personal / Exact Location Exposure</option>
              <option value="misinformation">Scientific / AQI Misinformation</option>
              <option value="unsafe_health_advice">Unsafe Health Advice</option>
              <option value="harassment_or_spam">Harassment or Spam</option>
            </select>
          </label>
          <label className="block text-xs font-medium">
            Concern Details
            <textarea
              rows={2}
              {...reportForm.register("details")}
              placeholder="Describe the concern for moderator review..."
              className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-xs"
            />
          </label>
          <button
            type="submit"
            disabled={reportPending}
            className="rounded bg-brand-primary px-3 py-1.5 text-xs font-semibold text-white dark:text-background"
          >
            Submit Report
          </button>
        </form>
      ) : null}
    </div>
  );
}

export function CommunityInitiativesCard({
  initiatives,
  isCurrentMember,
  activeInitiativeId,
  participationForm,
  participatePending,
  onToggleInitiative,
  onSubmitParticipation,
}: {
  initiatives: CommunityInitiative[];
  isCurrentMember: boolean;
  activeInitiativeId: string | null;
  participationForm: UseFormReturn<LogCommunityParticipationFormValues>;
  participatePending: boolean;
  onToggleInitiative: (id: string) => void;
  onSubmitParticipation: (values: LogCommunityParticipationFormValues) => void;
}) {
  const noteError = participationForm.formState.errors.note;
  return (
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
              {isCurrentMember ? (
                <button
                  type="button"
                  onClick={() => onToggleInitiative(init.id)}
                  className="rounded border border-text-secondary px-3 py-1 text-xs font-semibold"
                >
                  Log Voluntary Action
                </button>
              ) : null}

              {activeInitiativeId === init.id ? (
                <form
                  onSubmit={participationForm.handleSubmit(onSubmitParticipation)}
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
                  {noteError ? (
                    <p className="text-red-700 dark:text-red-300">{noteError.message}</p>
                  ) : null}
                  <button
                    type="submit"
                    disabled={participatePending}
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
  );
}
