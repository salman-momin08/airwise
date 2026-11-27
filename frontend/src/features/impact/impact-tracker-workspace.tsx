"use client";

import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ImpactEstimateCard } from "@/components/impact/impact-estimate-card";
import { ApiClientError } from "@/lib/api/client";
import { planningApi } from "@/lib/api/planning";
import {
  householdEnergyFormSchema,
  logActionFormSchema,
  type HouseholdEnergyFormValues,
  type LogActionFormValues,
} from "@/lib/validation/planning";
import type {
  ImpactEstimate,
  ImpactSummary,
  LoggedUserAction,
} from "@/types/planning";

function ImpactSummaryBanner({
  isLoading,
  unauthenticated,
  summary,
}: {
  isLoading: boolean;
  unauthenticated: boolean;
  summary: ImpactSummary | undefined;
}) {
  if (isLoading) {
    return (
      <div
        aria-busy="true"
        className="h-36 animate-pulse rounded-card border border-border bg-surface p-6"
      />
    );
  }
  if (unauthenticated) {
    return (
      <div role="status" className="rounded-card border border-border bg-surface p-6 text-sm">
        <p>
          <Link href="/login" className="font-semibold text-brand-primary underline">
            Sign in
          </Link>{" "}
          to view your cumulative avoided-CO₂e summary and save voluntary actions. Guest household
          energy calculations remain available below.
        </p>
      </div>
    );
  }
  if (!summary) {
    return null;
  }
  return (
    <section
      aria-label="Personal environmental impact summary"
      className="space-y-4 rounded-card border border-border bg-surface p-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Cumulative Self-Reported Impact Summary</h2>
        <span className="rounded-full border border-text-secondary px-2.5 py-0.5 text-xs font-semibold">
          Deterministic Estimates (is_estimate: true)
        </span>
      </div>

      <dl className="grid gap-4 sm:grid-cols-4">
        <div className="rounded-lg border border-border p-4">
          <dt className="text-xs text-text-secondary">Logged Actions</dt>
          <dd className="mt-1 text-2xl font-bold">{summary.total_logged_actions}</dd>
        </div>
        <div className="rounded-lg border border-brand-primary/50 bg-brand-accent/30 p-4">
          <dt className="text-xs text-text-secondary">Total Avoided CO₂e</dt>
          <dd className="mt-1 text-2xl font-bold">
            {summary.estimated_avoided_co2e_kg} <span className="text-xs font-normal">kg</span>
          </dd>
        </div>
        <div className="rounded-lg border border-border p-4">
          <dt className="text-xs text-text-secondary">Transport Avoided</dt>
          <dd className="mt-1 text-2xl font-bold">
            {summary.transport_avoided_co2e_kg} <span className="text-xs font-normal">kg</span>
          </dd>
        </div>
        <div className="rounded-lg border border-border p-4">
          <dt className="text-xs text-text-secondary">Energy Avoided</dt>
          <dd className="mt-1 text-2xl font-bold">
            {summary.energy_avoided_co2e_kg} <span className="text-xs font-normal">kg</span>
          </dd>
        </div>
      </dl>

      <p className="text-xs text-text-secondary">{summary.methodology_disclaimer}</p>
    </section>
  );
}

function LoggedActionHistorySection({ history }: { history: LoggedUserAction[] }) {
  return (
    <section
      aria-label="Logged action history"
      className="space-y-3 rounded-card border border-border bg-surface p-6"
    >
      <h2 className="text-base font-semibold">Recent Self-Reported Actions</h2>
      {history.length === 0 ? (
        <p className="text-sm text-text-secondary">
          No actions logged yet. Compare a commute on Sustainable Transport or log a household
          action above.
        </p>
      ) : (
        <ul className="space-y-3 text-sm">
          {history.map((item) => (
            <li
              key={item.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border p-3"
            >
              <div>
                <p className="font-medium text-text-primary">{item.title}</p>
                <p className="text-xs text-text-secondary">
                  {item.quantity} {item.unit} · Self-reported ·{" "}
                  {new Date(item.occurred_at).toLocaleString()}
                </p>
              </div>
              {item.impact_estimate ? (
                <span className="rounded-full border border-brand-primary/60 bg-brand-accent/40 px-3 py-1 text-xs font-semibold">
                  Est. Δ {item.impact_estimate.estimated_difference} {item.impact_estimate.unit}
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function ImpactTrackerWorkspace() {
  const queryClient = useQueryClient();
  const [energyEstimate, setEnergyEstimate] = useState<ImpactEstimate | null>(null);

  const summaryQuery = useQuery({
    queryKey: ["impact", "summary"],
    queryFn: () => planningApi.getImpactSummary(),
    retry: false,
  });

  const historyQuery = useQuery({
    queryKey: ["impact", "history"],
    queryFn: () => planningApi.getImpactHistory(),
    retry: false,
  });

  const energyForm = useForm<HouseholdEnergyFormValues>({
    resolver: zodResolver(householdEnergyFormSchema),
    defaultValues: {
      baseline_power_kw: 1.8,
      alternative_power_kw: 1.1,
      operating_hours: 4,
      grid_region_code: "india_cea_grid_avg",
    },
  });

  const actionForm = useForm<LogActionFormValues>({
    resolver: zodResolver(logActionFormSchema),
    defaultValues: {
      action_type: "public_transit_trip",
      title: "",
      quantity: 10,
      unit: "km",
    },
  });

  const energyMutation = useMutation({
    mutationFn: (values: HouseholdEnergyFormValues) =>
      planningApi.calculateImpact({
        calculator_type: "household_energy",
        ...values,
      }),
    onSuccess: (res) => setEnergyEstimate(res.data),
  });

  const logActionMutation = useMutation({
    mutationFn: (values: LogActionFormValues) =>
      planningApi.logUserAction({
        ...values,
        calculation:
          values.action_type === "appliance_load_reduction"
            ? {
                calculator_type: "household_energy",
                ...energyForm.getValues(),
              }
            : undefined,
      }),
    onSuccess: async () => {
      actionForm.reset({
        action_type: "public_transit_trip",
        title: "",
        quantity: 10,
        unit: "km",
      });
      await queryClient.invalidateQueries({ queryKey: ["impact"] });
    },
  });

  const unauthenticated =
    summaryQuery.isError &&
    summaryQuery.error instanceof ApiClientError &&
    summaryQuery.error.status === 401;

  const summary = summaryQuery.data?.data;
  const history = historyQuery.data?.data ?? [];

  const titleError = actionForm.formState.errors.title;

  return (
    <div className="mt-6 space-y-6 text-text-primary">
      <ImpactSummaryBanner
        isLoading={summaryQuery.isLoading}
        unauthenticated={unauthenticated}
        summary={summary}
      />

      <form
        onSubmit={energyForm.handleSubmit((vals) => energyMutation.mutate(vals))}
        className="space-y-4 rounded-card border border-border bg-surface p-6"
      >
        <h2 className="text-lg font-semibold">Household Electricity &amp; Energy CO₂e Calculator</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <label className="text-sm font-medium">
            Baseline Power (kW)
            <input
              type="number"
              step="0.1"
              {...energyForm.register("baseline_power_kw")}
              className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
            />
          </label>
          <label className="text-sm font-medium">
            Alternative Power (kW)
            <input
              type="number"
              step="0.1"
              {...energyForm.register("alternative_power_kw")}
              className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
            />
          </label>
          <label className="text-sm font-medium">
            Operating Hours
            <input
              type="number"
              step="0.5"
              {...energyForm.register("operating_hours")}
              className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
            />
          </label>
          <label className="text-sm font-medium">
            Grid Factor Region
            <select
              {...energyForm.register("grid_region_code")}
              className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
            >
              <option value="india_cea_grid_avg">India CEA Grid Average</option>
              <option value="us_epa_egrid_avg">US EPA eGRID Average</option>
            </select>
          </label>
        </div>
        <button
          type="submit"
          disabled={energyMutation.isPending}
          className="rounded bg-brand-primary px-4 py-2 text-sm font-semibold text-white dark:text-background disabled:opacity-60"
        >
          {energyMutation.isPending ? "Calculating..." : "Calculate Energy CO₂e Difference"}
        </button>
      </form>

      {energyEstimate ? (
        <ImpactEstimateCard
          estimate={energyEstimate}
          heading="Household Electricity CO₂e Estimate"
        />
      ) : null}

      {!unauthenticated ? (
        <form
          onSubmit={actionForm.handleSubmit((vals) => logActionMutation.mutate(vals))}
          className="space-y-4 rounded-card border border-border bg-surface p-6"
        >
          <h2 className="text-lg font-semibold">Log Voluntary Protective or Low-Emission Action</h2>
          <p className="text-xs text-text-secondary">
            Logged actions are clearly marked <code>is_self_reported: true</code> and never
            misrepresented as verified ambient air sensor measurements.
          </p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <label className="text-sm font-medium">
              Action Type
              <select
                {...actionForm.register("action_type")}
                className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
              >
                <option value="public_transit_trip">Public Transit Trip</option>
                <option value="carpool_trip">Shared Carpool Trip</option>
                <option value="work_from_home">Work from Home</option>
                <option value="hepa_filtration_session">HEPA Filtration Session</option>
                <option value="appliance_load_reduction">Appliance Load Reduction</option>
                <option value="smoke_free_cooking_ventilation">
                  Smoke-Free Cooking Exhaust
                </option>
              </select>
            </label>
            <label className="text-sm font-medium sm:col-span-2">
              Description
              <input
                {...actionForm.register("title")}
                placeholder="e.g., Used metro rail instead of solo driving"
                className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
              />
            </label>
            <div className="grid grid-cols-2 gap-2">
              <label className="text-sm font-medium">
                Quantity
                <input
                  type="number"
                  step="0.5"
                  {...actionForm.register("quantity")}
                  className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
                />
              </label>
              <label className="text-sm font-medium">
                Unit
                <input
                  {...actionForm.register("unit")}
                  className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
                />
              </label>
            </div>
          </div>
          {titleError ? (
            <p className="text-xs text-red-700 dark:text-red-300">{titleError.message}</p>
          ) : null}
          <button
            type="submit"
            disabled={logActionMutation.isPending}
            className="rounded bg-brand-primary px-4 py-2 text-sm font-semibold text-white dark:text-background disabled:opacity-60"
          >
            {logActionMutation.isPending ? "Saving Action..." : "Save Self-Reported Action"}
          </button>
        </form>
      ) : null}

      {!unauthenticated ? <LoggedActionHistorySection history={history} /> : null}
    </div>
  );
}
