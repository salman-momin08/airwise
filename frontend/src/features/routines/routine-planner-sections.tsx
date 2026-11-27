"use client";

/**
 * Presentational sections for the Daily Routine Planner workspace.
 */

import type { UseFormReturn } from "react-hook-form";
import { AQIBadge } from "@/components/air-quality/aqi-badge";
import { ProvenanceBanner } from "@/components/air-quality/provenance-banner";
import { ImpactEstimateCard } from "@/components/impact/impact-estimate-card";
import type { GenerateRoutineFormValues } from "@/lib/validation/planning";
import type {
  DailyRoutine,
  EnvironmentType,
  RoutineActivityEditable,
} from "@/types/planning";

/** Selector and explicit confirmation action bar for saved daily routines. */
export function SavedRoutineSelectorBar({
  routines,
  activeRoutine,
  hasUnsavedEdits,
  updatePending,
  deletePending,
  onSelectRoutine,
  onSaveSlots,
  onConfirmRoutine,
  onDeleteRoutine,
}: {
  routines: DailyRoutine[];
  activeRoutine: DailyRoutine | undefined;
  hasUnsavedEdits: boolean;
  updatePending: boolean;
  deletePending: boolean;
  onSelectRoutine: (id: string) => void;
  onSaveSlots: () => void;
  onConfirmRoutine: () => void;
  onDeleteRoutine: () => void;
}) {
  if (routines.length === 0) {
    return (
      <p className="rounded-card border border-border bg-surface p-6 text-sm text-text-secondary">
        No daily routines saved yet. Generate a Morning–Night draft above to inspect smog-safe
        activity blocks.
      </p>
    );
  }
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-border bg-surface p-4">
      <label className="text-sm font-medium">
        Saved Routines
        <select
          value={activeRoutine?.id ?? ""}
          onChange={(e) => onSelectRoutine(e.target.value)}
          className="ml-2 rounded border border-text-secondary bg-surface p-2 text-sm"
        >
          {routines.map((item) => (
            <option key={item.id} value={item.id}>
              {item.plan_date} · {item.city} ({item.status.toUpperCase()})
            </option>
          ))}
        </select>
      </label>

      {activeRoutine ? (
        <div className="flex flex-wrap gap-2">
          {hasUnsavedEdits ? (
            <button
              type="button"
              disabled={updatePending}
              onClick={onSaveSlots}
              className="rounded border border-text-secondary px-3 py-1.5 text-xs font-semibold"
            >
              Save Slot Edits
            </button>
          ) : null}

          {activeRoutine.status !== "confirmed" ? (
            <button
              type="button"
              disabled={updatePending}
              onClick={onConfirmRoutine}
              className="rounded bg-brand-primary px-3 py-1.5 text-xs font-semibold text-white dark:text-background"
            >
              Confirm &amp; Save Schedule
            </button>
          ) : null}

          <button
            type="button"
            disabled={deletePending}
            onClick={onDeleteRoutine}
            className="rounded border border-text-secondary px-3 py-1.5 text-xs font-medium"
          >
            Delete Routine
          </button>
        </div>
      ) : null}
    </div>
  );
}

/** Editable Morning–Night routine timeline displaying AQI snapshot provenance and warnings. */
export function ActiveRoutineTimelineSection({
  routine,
  editedSlots,
  onUpdateSlotField,
}: {
  routine: DailyRoutine;
  editedSlots: RoutineActivityEditable[];
  onUpdateSlotField: <K extends keyof RoutineActivityEditable>(
    idx: number,
    key: K,
    value: RoutineActivityEditable[K],
  ) => void;
}) {
  const envSummary = routine.environmental_summary;
  return (
    <section aria-label="Active daily routine timeline" className="space-y-4">
      {routine.requires_explicit_confirmation ? (
        <div
          role="status"
          className="rounded-lg border border-amber-500/70 bg-amber-100/80 px-4 py-3 text-sm text-amber-950 dark:bg-amber-900/30 dark:text-amber-100"
        >
          <strong>Unconfirmed Draft:</strong> AirWise never alters your confirmed schedule
          automatically. Review the time slots below and click{" "}
          <strong>Confirm &amp; Save Schedule</strong> when ready.
        </div>
      ) : (
        <div
          role="status"
          className="rounded-lg border border-brand-secondary/70 bg-brand-accent/40 px-4 py-2.5 text-xs font-semibold"
        >
          Status: Confirmed Schedule ({routine.plan_date})
        </div>
      )}

      {envSummary ? (
        <div className="space-y-3 rounded-card border border-border bg-surface p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-base font-semibold">Snapshot Provenance · {envSummary.city}</h3>
            <AQIBadge
              standard={envSummary.standard}
              aqi={envSummary.aqi}
              category={envSummary.category}
            />
          </div>
          <ProvenanceBanner
            provider={envSummary.provider}
            sourceType={envSummary.source_type}
            measuredAt={envSummary.measured_at}
            isStale={envSummary.is_stale}
            isDevelopmentFixture={envSummary.is_development_fixture}
          />
          <p className="text-xs text-text-secondary">
            <strong className="text-text-primary">Ventilation Rule:</strong>{" "}
            {envSummary.ventilation_guidance}
          </p>
          <p className="text-xs text-text-secondary">{envSummary.indoor_air_disclaimer}</p>
        </div>
      ) : null}

      <ol className="space-y-4">
        {routine.activities.map((activity, idx) => {
          const draftSlot = editedSlots[idx];
          return (
            <li
              key={activity.id}
              className="space-y-3 rounded-card border border-border bg-surface p-5"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-bold uppercase tracking-wide text-brand-primary">
                  {activity.time_block} Block
                </span>
                <span className="text-xs text-text-secondary">
                  Confidence: {activity.confidence}
                </span>
              </div>

              {activity.safety_warning ? (
                <div
                  role="alert"
                  className="rounded-lg border border-red-600/80 bg-red-100/90 p-3 text-xs font-medium text-red-950 dark:bg-red-950/50 dark:text-red-100"
                >
                  {activity.safety_warning}
                </div>
              ) : null}

              {draftSlot ? (
                <div className="grid gap-3 sm:grid-cols-4">
                  <label className="text-xs font-medium sm:col-span-2">
                    Activity Title
                    <input
                      value={draftSlot.title}
                      onChange={(e) => onUpdateSlotField(idx, "title", e.target.value)}
                      className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
                    />
                  </label>
                  <label className="text-xs font-medium">
                    Start Time (HH:MM)
                    <input
                      value={draftSlot.start_time}
                      onChange={(e) => onUpdateSlotField(idx, "start_time", e.target.value)}
                      className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
                    />
                  </label>
                  <label className="text-xs font-medium">
                    Environment
                    <select
                      value={draftSlot.environment_type}
                      onChange={(e) =>
                        onUpdateSlotField(
                          idx,
                          "environment_type",
                          e.target.value as EnvironmentType,
                        )
                      }
                      className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
                    >
                      <option value="indoor">Indoor</option>
                      <option value="transit">Enclosed Transit</option>
                      <option value="outdoor">Outdoor</option>
                    </select>
                  </label>
                </div>
              ) : null}

              <p className="text-sm text-text-primary">{activity.exposure_note}</p>
              <p className="text-xs text-text-secondary">{activity.explanation}</p>
              {activity.safer_alternative ? (
                <p className="text-xs text-text-secondary">
                  <strong className="text-text-primary">Safer Alternative:</strong>{" "}
                  {activity.safer_alternative}
                </p>
              ) : null}

              {activity.impact_estimate ? (
                <ImpactEstimateCard
                  estimate={activity.impact_estimate}
                  heading="Slot Impact & Exposure Estimate"
                />
              ) : null}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/** Form card generating a new unconfirmed Morning–Night draft routine. */
export function GenerateRoutineFormCard({
  form,
  isPending,
  onSubmit,
}: {
  form: UseFormReturn<GenerateRoutineFormValues>;
  isPending: boolean;
  onSubmit: (vals: GenerateRoutineFormValues) => void;
}) {
  const errors = form.formState.errors;
  return (
    <form
      onSubmit={form.handleSubmit(onSubmit)}
      className="space-y-4 rounded-card border border-border bg-surface p-6"
    >
      <h2 className="text-lg font-semibold">Generate Smog-Safe Draft Routine</h2>
      <p className="text-xs text-text-secondary">
        Priority order: 1. Exposure Safety → 2. Your Schedule Constraints → 3. Feasibility → 4.
        Emission Reduction → 5. Cost → 6. Convenience. New plans always start as a{" "}
        <strong>Draft</strong> until you confirm them.
      </p>

      <div className="grid gap-4 sm:grid-cols-3">
        <div>
          <label htmlFor="routine-city" className="block text-sm font-medium">
            City
          </label>
          <input
            id="routine-city"
            {...form.register("city")}
            aria-invalid={Boolean(errors.city)}
            aria-describedby={errors.city ? "routine-city-error" : undefined}
            className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
          />
          {errors.city ? (
            <p id="routine-city-error" className="mt-1 text-xs text-red-700 dark:text-red-300">
              {errors.city.message}
            </p>
          ) : null}
        </div>

        <div>
          <label htmlFor="routine-standard" className="block text-sm font-medium">
            AQI Standard
          </label>
          <select
            id="routine-standard"
            {...form.register("standard")}
            className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
          >
            <option value="india_naqi">India NAQI</option>
            <option value="us_epa">US EPA</option>
          </select>
        </div>

        <div>
          <label htmlFor="routine-distance" className="block text-sm font-medium">
            One-Way Commute (km)
          </label>
          <input
            id="routine-distance"
            type="number"
            step="0.5"
            {...form.register("commute_distance_km")}
            aria-invalid={Boolean(errors.commute_distance_km)}
            aria-describedby={errors.commute_distance_km ? "routine-distance-error" : undefined}
            className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
          />
          {errors.commute_distance_km ? (
            <p
              id="routine-distance-error"
              className="mt-1 text-xs text-red-700 dark:text-red-300"
            >
              {errors.commute_distance_km.message}
            </p>
          ) : null}
        </div>
      </div>

      <button
        type="submit"
        disabled={isPending}
        className="rounded bg-brand-primary px-4 py-2 text-sm font-semibold text-white dark:text-background disabled:opacity-60"
      >
        {isPending ? "Generating Draft..." : "Generate Morning–Night Draft"}
      </button>
    </form>
  );
}
