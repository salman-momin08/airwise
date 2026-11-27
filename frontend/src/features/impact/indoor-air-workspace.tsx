"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AQIBadge } from "@/components/air-quality/aqi-badge";
import { ProvenanceBanner } from "@/components/air-quality/provenance-banner";
import { ImpactEstimateCard } from "@/components/impact/impact-estimate-card";
import { airQualityApi } from "@/lib/api/air-quality";
import { planningApi } from "@/lib/api/planning";
import {
  indoorFiltrationFormSchema,
  type IndoorFiltrationFormValues,
} from "@/lib/validation/planning";
import { useLocationStore } from "@/stores/location-store";
import type { ImpactEstimate } from "@/types/planning";

export function IndoorAirWorkspace() {
  const city = useLocationStore((s) => s.selectedCity);
  const standard = useLocationStore((s) => s.aqiStandard);
  const [estimate, setEstimate] = useState<ImpactEstimate | null>(null);

  const outdoorQuery = useQuery({
    queryKey: ["air-quality", "current", city, standard],
    queryFn: () => airQualityApi.getCurrent(city, standard),
  });

  const form = useForm<IndoorFiltrationFormValues>({
    resolver: zodResolver(indoorFiltrationFormSchema),
    defaultValues: {
      room_area_m2: 18,
      ceiling_height_m: 2.7,
      cadr_m3_per_hour: 250,
      has_active_indoor_smoke: false,
    },
  });

  const calcMutation = useMutation({
    mutationFn: (values: IndoorFiltrationFormValues) =>
      planningApi.calculateImpact({
        calculator_type: "indoor_filtration",
        ...values,
      }),
    onSuccess: (res) => setEstimate(res.data),
  });

  const errors = form.formState.errors;
  const current = outdoorQuery.data?.data;

  return (
    <div className="mt-6 space-y-6 text-text-primary">
      <div
        role="status"
        className="rounded-card border border-amber-500/70 bg-amber-100/80 p-5 text-sm text-amber-950 dark:bg-amber-900/30 dark:text-amber-100"
      >
        <p className="font-semibold">
          Indoor Air Quality Status: Unmeasured (No Indoor PM2.5 Sensor Connected)
        </p>
        <p className="mt-1 text-xs">
          AirWise never guesses indoor PM2.5 solely from outdoor station readings. Below is
          evidence-backed general protection guidance and deterministic room-volume HEPA CADR/ACH
          sizing.
        </p>
      </div>

      <section
        aria-label="Outdoor make-up air context"
        className="space-y-3 rounded-card border border-border bg-surface p-5"
      >
        <h2 className="text-base font-semibold">
          Outdoor Window-Ventilation Context ({city})
        </h2>
        {outdoorQuery.isLoading ? (
          <div aria-busy="true" className="h-16 animate-pulse rounded bg-background" />
        ) : current ? (
          <div className="space-y-3">
            <AQIBadge
              standard={current.standard}
              aqi={current.aqi}
              category={current.category}
            />
            <p className="text-sm text-text-secondary">{current.precaution_summary}</p>
            <ProvenanceBanner
              provider={current.provider}
              sourceType={current.source_type}
              measuredAt={current.measured_at}
              isStale={current.is_stale}
              isDevelopmentFixture={current.is_development_fixture}
            />
          </div>
        ) : (
          <p className="text-sm text-text-secondary">
            Live outdoor station context is currently unavailable; keep exterior windows closed if
            outdoor haze or smoke odor is present.
          </p>
        )}
      </section>

      <form
        onSubmit={form.handleSubmit((vals) => calcMutation.mutate(vals))}
        className="space-y-4 rounded-card border border-border bg-surface p-6"
      >
        <h2 className="text-lg font-semibold">
          Deterministic HEPA Purifier CADR &amp; Room ACH Calculator
        </h2>
        <p className="text-xs text-text-secondary">
          Target at least 4–5 clean air changes per hour (ACH) in bedrooms during winter smog.
        </p>

        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <label htmlFor="iaq-area" className="block text-sm font-medium">
              Room Floor Area (m²)
            </label>
            <input
              id="iaq-area"
              type="number"
              step="0.5"
              {...form.register("room_area_m2")}
              aria-invalid={Boolean(errors.room_area_m2)}
              aria-describedby={errors.room_area_m2 ? "iaq-area-error" : undefined}
              className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
            />
            {errors.room_area_m2 ? (
              <p id="iaq-area-error" className="mt-1 text-xs text-red-700 dark:text-red-300">
                {errors.room_area_m2.message}
              </p>
            ) : null}
          </div>

          <div>
            <label htmlFor="iaq-height" className="block text-sm font-medium">
              Ceiling Height (m)
            </label>
            <input
              id="iaq-height"
              type="number"
              step="0.1"
              {...form.register("ceiling_height_m")}
              aria-invalid={Boolean(errors.ceiling_height_m)}
              aria-describedby={errors.ceiling_height_m ? "iaq-height-error" : undefined}
              className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
            />
            {errors.ceiling_height_m ? (
              <p id="iaq-height-error" className="mt-1 text-xs text-red-700 dark:text-red-300">
                {errors.ceiling_height_m.message}
              </p>
            ) : null}
          </div>

          <div>
            <label htmlFor="iaq-cadr" className="block text-sm font-medium">
              Purifier Smoke/Dust CADR (m³/h)
            </label>
            <input
              id="iaq-cadr"
              type="number"
              step="10"
              {...form.register("cadr_m3_per_hour")}
              aria-invalid={Boolean(errors.cadr_m3_per_hour)}
              aria-describedby={errors.cadr_m3_per_hour ? "iaq-cadr-error" : undefined}
              className="mt-1 w-full rounded border border-text-secondary bg-surface p-2 text-sm"
            />
            {errors.cadr_m3_per_hour ? (
              <p id="iaq-cadr-error" className="mt-1 text-xs text-red-700 dark:text-red-300">
                {errors.cadr_m3_per_hour.message}
              </p>
            ) : null}
          </div>
        </div>

        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...form.register("has_active_indoor_smoke")} />
          Active indoor smoke source present (incense, mosquito coils, smoking, or unvented stove)
        </label>

        <button
          type="submit"
          disabled={calcMutation.isPending}
          className="rounded bg-brand-primary px-4 py-2 text-sm font-semibold text-white dark:text-background disabled:opacity-60"
        >
          {calcMutation.isPending ? "Calculating..." : "Calculate Clean Air Changes (ACH)"}
        </button>
      </form>

      {estimate ? (
        <ImpactEstimateCard
          estimate={estimate}
          heading="Room Filtration ACH & Steady-State Particle Ratio Estimate"
        />
      ) : null}

      <section
        aria-label="Evidence-based indoor air checklist"
        className="grid gap-4 sm:grid-cols-2"
      >
        <div className="rounded-card border border-border bg-surface p-5 text-sm">
          <h3 className="font-semibold text-text-primary">Evidence-Backed Protection Steps</h3>
          <ul className="mt-2 list-inside list-disc space-y-1.5 text-xs text-text-secondary">
            <li>Eliminate indoor combustion first: tobacco, incense, candles, and coils.</li>
            <li>Run kitchen exhaust hoods vented outdoors whenever frying or simmering.</li>
            <li>Use wet mopping and damp microfiber cloths so settled dust is not resuspended.</li>
            <li>Keep bedroom doors and exterior windows closed while running a HEPA unit.</li>
          </ul>
        </div>
        <div className="rounded-card border border-border bg-surface p-5 text-sm">
          <h3 className="font-semibold text-text-primary">Scientific Guardrails (What to Avoid)</h3>
          <ul className="mt-2 list-inside list-disc space-y-1.5 text-xs text-text-secondary">
            <li>
              <strong>No ozone/ionizer cleaners:</strong> Ozone irritates airways and worsens
              indoor air quality.
            </li>
            <li>
              <strong>No houseplant PM2.5 myths:</strong> Potted plants do not meaningfully filter
              fine winter smog particles at household ventilation rates.
            </li>
            <li>
              <strong>Honest limits:</strong> Portable HEPA filtration lowers indoor particle
              levels but never eliminates 100% of exposure.
            </li>
          </ul>
        </div>
      </section>
    </div>
  );
}
