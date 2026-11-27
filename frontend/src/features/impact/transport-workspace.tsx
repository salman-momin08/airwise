"use client";

/**
 * Exposure-screened commute comparison calculator and verified emission-factors table.
 */

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ImpactEstimateCard } from "@/components/impact/impact-estimate-card";
import { ApiClientError } from "@/lib/api/client";
import { COMMUTE_MODE_OPTIONS } from "@/lib/constants/commute-modes";
import { planningApi } from "@/lib/api/planning";
import {
  transportCompareFormSchema,
  type TransportCompareFormValues,
} from "@/lib/validation/planning";
import { useLocationStore } from "@/stores/location-store";
import type { EmissionFactor, ImpactEstimate } from "@/types/planning";

function mapAlternativeToActionType(
  mode: TransportCompareFormValues["alternative_mode"],
): "carpool_trip" | "work_from_home" | "public_transit_trip" {
  if (mode === "carpool_3") return "carpool_trip";
  if (mode === "work_from_home") return "work_from_home";
  return "public_transit_trip";
}

function ReferenceFactorsSection({
  factors,
  isLoading,
  isError,
}: {
  factors: EmissionFactor[];
  isLoading: boolean;
  isError: boolean;
}) {
  return (
    <section
      aria-label="Reference transport emission factors"
      className="space-y-3 rounded-card border border-border bg-surface p-6"
    >
      <h2 className="text-base font-semibold">Verified Reference Transport Factors</h2>
      {isLoading ? (
        <div aria-busy="true" className="h-24 animate-pulse rounded bg-background" />
      ) : isError ? (
        <p role="alert" className="text-sm text-text-secondary">
          Unable to load reference emission factors.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <caption className="sr-only">
              Verified reference transport emission factors and exposure profiles
            </caption>
            <thead>
              <tr className="border-b border-border text-text-secondary">
                <th scope="col" className="py-2 pr-4">
                  Mode
                </th>
                <th scope="col" className="py-2 pr-4">
                  Factor
                </th>
                <th scope="col" className="py-2 pr-4">
                  Default Occupancy
                </th>
                <th scope="col" className="py-2 pr-4">
                  Exposure Profile
                </th>
                <th scope="col" className="py-2">
                  Reference Source
                </th>
              </tr>
            </thead>
            <tbody>
              {factors.map((f) => (
                <tr key={f.mode_or_region_code} className="border-b border-border/60">
                  <td className="py-2 pr-4 font-medium text-text-primary">{f.display_label}</td>
                  <td className="py-2 pr-4">
                    {f.factor_value} {f.unit}
                  </td>
                  <td className="py-2 pr-4">{f.default_occupancy ?? "—"}</td>
                  <td className="py-2 pr-4">
                    {f.is_active_outdoor_mode
                      ? "Open-air roadside (blocked in severe smog)"
                      : "Enclosed cabin / indoor"}
                  </td>
                  <td className="py-2 text-text-secondary">{f.source_reference}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function TripLogActionRow({
  isPending,
  loggedNote,
  isError,
  error,
  onLogTrip,
}: {
  isPending: boolean;
  loggedNote: string | null;
  isError: boolean;
  error: unknown;
  onLogTrip: () => void;
}) {
  const errText =
    error instanceof ApiClientError && error.status === 401
      ? "Sign in to save completed trips to your account history."
      : "Unable to log action right now.";
  return (
    <div className="flex flex-wrap items-center gap-3">
      <button
        type="button"
        disabled={isPending}
        onClick={onLogTrip}
        className="rounded border border-text-secondary bg-surface px-4 py-2 text-xs font-semibold"
      >
        {isPending ? "Logging..." : "Log This Trip to My Impact Tracker"}
      </button>
      {loggedNote ? (
        <span role="status" className="text-xs font-medium text-emerald-800 dark:text-emerald-300">
          {loggedNote}
        </span>
      ) : null}
      {isError ? (
        <span role="alert" className="text-xs text-red-700 dark:text-red-300">
          {errText}
        </span>
      ) : null}
    </div>
  );
}

function TransportCompareFormCard({
  form,
  isPending,
  onSubmit,
}: {
  form: ReturnType<typeof useForm<TransportCompareFormValues>>;
  isPending: boolean;
  onSubmit: (vals: TransportCompareFormValues) => void;
}) {
  const errors = form.formState.errors;
  return (
    <form
      onSubmit={form.handleSubmit(onSubmit)}
      className="space-y-4 rounded-card border border-border bg-surface p-6"
    >
      <h2 className="text-lg font-semibold">
        Exposure-Screened Commute &amp; CO₂e Comparison
      </h2>
      <p className="text-xs text-text-secondary">
        AirWise evaluates live outdoor pollution exposure first. Walking, cycling, or open
        two-wheelers are never recommended during poor or severe smog solely to save tailpipe
        CO₂e.
      </p>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <label htmlFor="tx-city" className="block text-sm font-medium">
            City (for Live Exposure Check)
          </label>
          <input
            id="tx-city"
            {...form.register("city")}
            aria-invalid={Boolean(errors.city)}
            aria-describedby={errors.city ? "tx-city-error" : undefined}
            className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
          />
          {errors.city ? (
            <p id="tx-city-error" className="mt-1 text-xs text-red-700 dark:text-red-300">
              {errors.city.message}
            </p>
          ) : null}
        </div>

        <div>
          <label htmlFor="tx-standard" className="block text-sm font-medium">
            AQI Standard
          </label>
          <select
            id="tx-standard"
            {...form.register("standard")}
            className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
          >
            <option value="india_naqi">India NAQI</option>
            <option value="us_epa">US EPA</option>
          </select>
        </div>

        <div>
          <label htmlFor="tx-distance" className="block text-sm font-medium">
            Trip Distance (km)
          </label>
          <input
            id="tx-distance"
            type="number"
            step="0.5"
            {...form.register("distance_km")}
            aria-invalid={Boolean(errors.distance_km)}
            aria-describedby={errors.distance_km ? "tx-distance-error" : undefined}
            className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
          />
          {errors.distance_km ? (
            <p id="tx-distance-error" className="mt-1 text-xs text-red-700 dark:text-red-300">
              {errors.distance_km.message}
            </p>
          ) : null}
        </div>

        <div>
          <label htmlFor="tx-baseline" className="block text-sm font-medium">
            Baseline Mode
          </label>
          <select
            id="tx-baseline"
            {...form.register("baseline_mode")}
            className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
          >
            {COMMUTE_MODE_OPTIONS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="tx-alternative" className="block text-sm font-medium">
            Candidate Alternative Mode
          </label>
          <select
            id="tx-alternative"
            {...form.register("alternative_mode")}
            className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
          >
            {COMMUTE_MODE_OPTIONS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <button
        type="submit"
        disabled={isPending}
        className="rounded bg-brand-primary px-4 py-2 text-sm font-semibold text-white dark:text-background disabled:opacity-60"
      >
        {isPending ? "Calculating..." : "Compare Exposure & CO₂e"}
      </button>
    </form>
  );
}

export function TransportWorkspace() {
  const queryClient = useQueryClient();
  const storeCity = useLocationStore((s) => s.selectedCity);
  const storeStandard = useLocationStore((s) => s.aqiStandard);
  const [estimate, setEstimate] = useState<ImpactEstimate | null>(null);
  const [loggedNote, setLoggedNote] = useState<string | null>(null);

  const factorsQuery = useQuery({
    queryKey: ["impact", "factors", "transport"],
    queryFn: () => planningApi.listEmissionFactors("transport"),
  });

  const form = useForm<TransportCompareFormValues>({
    resolver: zodResolver(transportCompareFormSchema),
    defaultValues: {
      city: storeCity,
      standard: storeStandard,
      distance_km: 12,
      baseline_mode: "car_solo_petrol",
      alternative_mode: "metro_rail",
    },
  });

  const compareMutation = useMutation({
    mutationFn: (values: TransportCompareFormValues) =>
      planningApi.calculateImpact({
        calculator_type: "transport",
        ...values,
      }),
    onSuccess: (res) => {
      setEstimate(res.data);
      setLoggedNote(null);
    },
  });

  const logMutation = useMutation({
    mutationFn: () => {
      const vals = form.getValues();
      return planningApi.logUserAction({
        action_type: mapAlternativeToActionType(vals.alternative_mode),
        title: `Switched ${vals.distance_km} km commute from ${vals.baseline_mode} to ${vals.alternative_mode}`,
        quantity: vals.distance_km,
        unit: "km",
        calculation: {
          calculator_type: "transport",
          ...vals,
        },
      });
    },
    onSuccess: async () => {
      setLoggedNote("Self-reported commute action logged to your Impact Tracker.");
      await queryClient.invalidateQueries({ queryKey: ["impact"] });
    },
  });

  const compareErrorText =
    compareMutation.error instanceof Error
      ? compareMutation.error.message
      : "Calculation failed.";

  return (
    <div className="mt-6 space-y-6 text-text-primary">
      <TransportCompareFormCard
        form={form}
        isPending={compareMutation.isPending}
        onSubmit={(vals) => compareMutation.mutate(vals)}
      />

      {compareMutation.isError ? (
        <div role="alert" className="rounded-lg border border-red-600/80 p-4 text-sm">
          {compareErrorText}
        </div>
      ) : null}

      {estimate ? (
        <div className="space-y-3">
          <ImpactEstimateCard
            estimate={estimate}
            heading="Passenger-Kilometer CO₂e & Exposure Screening Result"
          />
          {estimate.exposure_screening?.recommended_for_current_aqi !== false ? (
            <TripLogActionRow
              isPending={logMutation.isPending}
              loggedNote={loggedNote}
              isError={logMutation.isError}
              error={logMutation.error}
              onLogTrip={() => logMutation.mutate()}
            />
          ) : null}
        </div>
      ) : null}

      <ReferenceFactorsSection
        factors={factorsQuery.data?.data ?? []}
        isLoading={factorsQuery.isLoading}
        isError={factorsQuery.isError}
      />
    </div>
  );
}
