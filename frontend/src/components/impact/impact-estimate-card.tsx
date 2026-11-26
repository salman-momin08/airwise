import { AQIBadge } from "@/components/air-quality/aqi-badge";
import type { ImpactEstimate } from "@/types/planning";

const UNIT_LABELS: Record<string, string> = {
  kg_co2e: "kg CO₂e",
  clean_air_changes_per_hour: "ACH (clean air changes/hr)",
  ug_h_per_m3: "µg·h/m³ relative exposure index",
};

interface ImpactEstimateCardProps {
  estimate: ImpactEstimate;
  heading?: string;
}

export function ImpactEstimateCard({
  estimate,
  heading = "Deterministic Impact Estimate",
}: ImpactEstimateCardProps) {
  const unitLabel = UNIT_LABELS[estimate.unit] ?? estimate.unit;
  const screening = estimate.exposure_screening;

  return (
    <section
      aria-label={heading}
      className="space-y-4 rounded-card border border-border bg-surface p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-base font-semibold text-text-primary">{heading}</h3>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-full border border-text-secondary px-2.5 py-0.5 font-semibold text-text-primary">
            Model Estimate (is_estimate: true)
          </span>
          <span className="rounded-full border border-border px-2.5 py-0.5 text-text-secondary">
            Confidence: <strong className="text-text-primary">{estimate.confidence}</strong>
          </span>
        </div>
      </div>

      {screening && !screening.recommended_for_current_aqi && screening.exposure_warning ? (
        <div
          role="alert"
          className="space-y-2 rounded-lg border border-red-600/80 bg-red-100/90 p-4 text-sm text-red-950 dark:bg-red-950/50 dark:text-red-100"
        >
          <p className="font-semibold">{screening.exposure_warning}</p>
          {screening.safer_commute_fallback ? (
            <p>
              <strong>Safer Alternative:</strong> {screening.safer_commute_fallback}
            </p>
          ) : null}
        </div>
      ) : null}

      {screening && screening.recommended_for_current_aqi && screening.exposure_warning ? (
        <div
          role="status"
          className="rounded-lg border border-amber-500/70 bg-amber-100/80 px-4 py-2.5 text-xs font-medium text-amber-950 dark:bg-amber-900/30 dark:text-amber-100"
        >
          {screening.exposure_warning}
        </div>
      ) : null}

      {screening?.evaluated && screening.standard ? (
        <div className="flex flex-wrap items-center gap-3 text-xs text-text-secondary">
          <span>Exposure Screening Context ({screening.city}):</span>
          <AQIBadge
            standard={screening.standard}
            aqi={screening.aqi}
            category={screening.category}
          />
          {screening.is_development_fixture ? (
            <span className="font-medium text-amber-800 dark:text-amber-200">
              (Development Fixture Telemetry)
            </span>
          ) : null}
        </div>
      ) : null}

      <dl className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-lg border border-border p-3">
          <dt className="text-xs text-text-secondary">Baseline</dt>
          <dd className="mt-1 text-lg font-bold text-text-primary">
            {estimate.baseline_value} <span className="text-xs font-normal">{unitLabel}</span>
          </dd>
        </div>
        <div className="rounded-lg border border-border p-3">
          <dt className="text-xs text-text-secondary">Selected Option</dt>
          <dd className="mt-1 text-lg font-bold text-text-primary">
            {estimate.alternative_value} <span className="text-xs font-normal">{unitLabel}</span>
          </dd>
        </div>
        <div className="rounded-lg border border-brand-primary/50 bg-brand-accent/30 p-3">
          <dt className="text-xs text-text-secondary">Estimated Difference</dt>
          <dd className="mt-1 text-lg font-bold text-text-primary">
            {estimate.estimated_difference > 0 ? `+${estimate.estimated_difference}` : estimate.estimated_difference}{" "}
            <span className="text-xs font-normal">{unitLabel}</span>
          </dd>
        </div>
      </dl>

      <div className="space-y-2 text-xs text-text-secondary">
        <p>
          <strong className="text-text-primary">Methodology:</strong> {estimate.methodology}
        </p>
        <div>
          <strong className="text-text-primary">Explicit Assumptions:</strong>
          <ul className="mt-1 list-inside list-disc space-y-0.5">
            {estimate.assumptions.map((item, idx) => (
              <li key={idx}>{item}</li>
            ))}
          </ul>
        </div>
        <p>
          <strong className="text-text-primary">Reference Sources:</strong>{" "}
          {estimate.source_references.join(" · ")}
        </p>
      </div>
    </section>
  );
}
