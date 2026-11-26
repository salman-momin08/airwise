"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AQIBadge } from "@/components/air-quality/aqi-badge";
import { ProvenanceBanner } from "@/components/air-quality/provenance-banner";
import { ImpactEstimateCard } from "@/components/impact/impact-estimate-card";
import { ApiClientError } from "@/lib/api/client";
import { planningApi } from "@/lib/api/planning";
import {
  generateRoutineFormSchema,
  type GenerateRoutineFormValues,
} from "@/lib/validation/planning";
import { useLocationStore } from "@/stores/location-store";
import type {
  DailyRoutine,
  EnvironmentType,
  RoutineActivityEditable,
} from "@/types/planning";

export function RoutinePlannerWorkspace() {
  const queryClient = useQueryClient();
  const storeCity = useLocationStore((s) => s.selectedCity);
  const storeStandard = useLocationStore((s) => s.aqiStandard);

  const [selectedRoutineId, setSelectedRoutineId] = useState<string | null>(null);
  const [editedSlots, setEditedSlots] = useState<RoutineActivityEditable[]>([]);
  const [hasUnsavedEdits, setHasUnsavedEdits] = useState(false);
  const [feedbackBanner, setFeedbackBanner] = useState<string | null>(null);

  const routinesQuery = useQuery({
    queryKey: ["routines", "list"],
    queryFn: () => planningApi.listRoutines(),
    retry: false,
  });

  const form = useForm<GenerateRoutineFormValues>({
    resolver: zodResolver(generateRoutineFormSchema),
    defaultValues: {
      city: storeCity,
      standard: storeStandard,
      commute_distance_km: 10,
    },
  });

  const routines = routinesQuery.data?.data ?? [];
  const activeRoutine: DailyRoutine | undefined =
    routines.find((r) => r.id === selectedRoutineId) ?? routines[0];

  useEffect(() => {
    if (!activeRoutine) {
      setEditedSlots([]);
      setHasUnsavedEdits(false);
      return;
    }
    setSelectedRoutineId(activeRoutine.id);
    setEditedSlots(
      activeRoutine.activities.map((a) => ({
        time_block: a.time_block,
        start_time: a.start_time,
        duration_minutes: a.duration_minutes,
        title: a.title,
        environment_type: a.environment_type,
        safer_alternative: a.safer_alternative,
      })),
    );
    setHasUnsavedEdits(false);
  }, [activeRoutine]);

  const generateMutation = useMutation({
    mutationFn: (values: GenerateRoutineFormValues) => planningApi.generateRoutine(values),
    onSuccess: async (res) => {
      setSelectedRoutineId(res.data.id);
      setFeedbackBanner(
        "Draft routine generated. Review or customize slots below, then click Confirm & Save Schedule.",
      );
      await queryClient.invalidateQueries({ queryKey: ["routines", "list"] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: (vars: {
      routineId: string;
      status?: "draft" | "confirmed" | "archived";
      activities?: RoutineActivityEditable[];
    }) =>
      planningApi.updateRoutine(vars.routineId, {
        status: vars.status,
        activities: vars.activities,
      }),
    onSuccess: async (res) => {
      setFeedbackBanner(
        res.data.status === "confirmed"
          ? "Schedule explicitly confirmed and saved."
          : "Routine slots updated and screened against snapshot AQI.",
      );
      setHasUnsavedEdits(false);
      await queryClient.invalidateQueries({ queryKey: ["routines", "list"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (routineId: string) => planningApi.deleteRoutine(routineId),
    onSuccess: async () => {
      setSelectedRoutineId(null);
      setFeedbackBanner("Routine deleted.");
      await queryClient.invalidateQueries({ queryKey: ["routines", "list"] });
    },
  });

  if (routinesQuery.isLoading) {
    return (
      <div
        aria-busy="true"
        className="mt-6 h-64 animate-pulse rounded-card border border-border bg-surface p-6"
      />
    );
  }

  if (routinesQuery.isError) {
    const unauth =
      routinesQuery.error instanceof ApiClientError && routinesQuery.error.status === 401;
    return (
      <div role="alert" className="mt-6 rounded-card border border-border bg-surface p-6 text-sm">
        {unauth ? (
          <p>
            Please{" "}
            <Link href="/login" className="font-semibold text-brand-primary underline">
              sign in
            </Link>{" "}
            to generate, customize, and confirm personalized Morning–Night routines.
          </p>
        ) : (
          <div className="space-y-3">
            <p>Unable to load your saved routines.</p>
            <button
              type="button"
              onClick={() => void routinesQuery.refetch()}
              className="rounded border border-text-secondary px-3 py-1.5 font-medium"
            >
              Retry
            </button>
          </div>
        )}
      </div>
    );
  }

  const errors = form.formState.errors;
  const updateSlotField = <K extends keyof RoutineActivityEditable>(
    idx: number,
    key: K,
    value: RoutineActivityEditable[K],
  ) => {
    setEditedSlots((prev) =>
      prev.map((slot, i) => (i === idx ? { ...slot, [key]: value } : slot)),
    );
    setHasUnsavedEdits(true);
  };

  return (
    <div className="mt-6 space-y-6 text-text-primary">
      <form
        onSubmit={form.handleSubmit((vals) => generateMutation.mutate(vals))}
        className="space-y-4 rounded-card border border-border bg-surface p-6"
      >
        <h2 className="text-lg font-semibold">Generate Smog-Safe Draft Routine</h2>
        <p className="text-xs text-text-secondary">
          Priority order: 1. Exposure Safety → 2. Your Schedule Constraints → 3. Feasibility →
          4. Emission Reduction → 5. Cost → 6. Convenience. New plans always start as a{" "}
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
              aria-describedby="routine-city-error"
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
              aria-describedby="routine-distance-error"
              className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
            />
            {errors.commute_distance_km ? (
              <p id="routine-distance-error" className="mt-1 text-xs text-red-700 dark:text-red-300">
                {errors.commute_distance_km.message}
              </p>
            ) : null}
          </div>
        </div>

        <button
          type="submit"
          disabled={generateMutation.isPending}
          className="rounded bg-brand-primary px-4 py-2 text-sm font-semibold text-white dark:text-background disabled:opacity-60"
        >
          {generateMutation.isPending ? "Generating Draft..." : "Generate Morning–Night Draft"}
        </button>
      </form>

      {feedbackBanner ? (
        <div
          role="status"
          className="rounded-lg border border-brand-primary/60 bg-brand-accent/40 px-4 py-3 text-sm font-medium"
        >
          {feedbackBanner}
        </div>
      ) : null}

      {routines.length > 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-border bg-surface p-4">
          <label className="text-sm font-medium">
            Saved Routines
            <select
              value={activeRoutine?.id ?? ""}
              onChange={(e) => setSelectedRoutineId(e.target.value)}
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
                  disabled={updateMutation.isPending}
                  onClick={() =>
                    updateMutation.mutate({
                      routineId: activeRoutine.id,
                      activities: editedSlots,
                    })
                  }
                  className="rounded border border-text-secondary px-3 py-1.5 text-xs font-semibold"
                >
                  Save Slot Edits
                </button>
              ) : null}

              {activeRoutine.status !== "confirmed" ? (
                <button
                  type="button"
                  disabled={updateMutation.isPending}
                  onClick={() =>
                    updateMutation.mutate({
                      routineId: activeRoutine.id,
                      status: "confirmed",
                      activities: hasUnsavedEdits ? editedSlots : undefined,
                    })
                  }
                  className="rounded bg-brand-primary px-3 py-1.5 text-xs font-semibold text-white dark:text-background"
                >
                  Confirm &amp; Save Schedule
                </button>
              ) : null}

              <button
                type="button"
                disabled={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate(activeRoutine.id)}
                className="rounded border border-text-secondary px-3 py-1.5 text-xs font-medium"
              >
                Delete Routine
              </button>
            </div>
          ) : null}
        </div>
      ) : (
        <p className="rounded-card border border-border bg-surface p-6 text-sm text-text-secondary">
          No daily routines saved yet. Generate a Morning–Night draft above to inspect smog-safe
          activity blocks.
        </p>
      )}

      {activeRoutine ? (
        <section aria-label="Active daily routine timeline" className="space-y-4">
          {activeRoutine.requires_explicit_confirmation ? (
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
              Status: Confirmed Schedule ({activeRoutine.plan_date})
            </div>
          )}

          {activeRoutine.environmental_summary ? (
            <div className="space-y-3 rounded-card border border-border bg-surface p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h3 className="text-base font-semibold">
                  Snapshot Provenance · {activeRoutine.environmental_summary.city}
                </h3>
                <AQIBadge
                  standard={activeRoutine.environmental_summary.standard}
                  aqi={activeRoutine.environmental_summary.aqi}
                  category={activeRoutine.environmental_summary.category}
                />
              </div>
              <ProvenanceBanner
                provider={activeRoutine.environmental_summary.provider}
                sourceType={activeRoutine.environmental_summary.source_type}
                measuredAt={activeRoutine.environmental_summary.measured_at}
                isStale={activeRoutine.environmental_summary.is_stale}
                isDevelopmentFixture={
                  activeRoutine.environmental_summary.is_development_fixture
                }
              />
              <p className="text-xs text-text-secondary">
                <strong className="text-text-primary">Ventilation Rule:</strong>{" "}
                {activeRoutine.environmental_summary.ventilation_guidance}
              </p>
              <p className="text-xs text-text-secondary">
                {activeRoutine.environmental_summary.indoor_air_disclaimer}
              </p>
            </div>
          ) : null}

          <ol className="space-y-4">
            {activeRoutine.activities.map((activity, idx) => {
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
                          onChange={(e) => updateSlotField(idx, "title", e.target.value)}
                          className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
                        />
                      </label>
                      <label className="text-xs font-medium">
                        Start Time (HH:MM)
                        <input
                          value={draftSlot.start_time}
                          onChange={(e) => updateSlotField(idx, "start_time", e.target.value)}
                          className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
                        />
                      </label>
                      <label className="text-xs font-medium">
                        Environment
                        <select
                          value={draftSlot.environment_type}
                          onChange={(e) =>
                            updateSlotField(
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
      ) : null}
    </div>
  );
}
