import type { AQIStandard, PollutantCode, PollutantReading } from "@/types/api";

const POLLUTANT_META: Record<PollutantCode, { label: string; description: string }> = {
  pm25: {
    label: "PM2.5",
    description: "Fine inhalable particles (≤2.5 µm) — primary winter smog driver",
  },
  pm10: {
    label: "PM10",
    description: "Coarse inhalable dust & smoke particles (≤10 µm)",
  },
  no2: {
    label: "NO₂",
    description: "Nitrogen dioxide — road traffic & combustion indicator",
  },
  so2: {
    label: "SO₂",
    description: "Sulfur dioxide — industrial & fuel combustion gas",
  },
  co: {
    label: "CO",
    description: "Carbon monoxide — incomplete combustion gas",
  },
  o3: {
    label: "O₃",
    description: "Ground-level ozone — sunlight-driven photochemical oxidant",
  },
};

interface PollutantBreakdownGridProps {
  pollutants: PollutantReading[];
  dominantPollutant: PollutantCode | null;
  standard: AQIStandard;
}

export function PollutantBreakdownGrid({
  pollutants,
  dominantPollutant,
  standard,
}: PollutantBreakdownGridProps) {
  const stdLabel = standard === "india_naqi" ? "India NAQI" : "US EPA";

  if (pollutants.length === 0) {
    return (
      <p className="rounded-card border border-dashed border-border bg-surface p-5 text-sm text-text-secondary">
        Individual pollutant concentrations are currently unavailable for this location.
      </p>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {pollutants.map((item) => {
        const meta = POLLUTANT_META[item.pollutant];
        const isDominant = dominantPollutant === item.pollutant;
        return (
          <article
            key={item.pollutant}
            className={`rounded-card border p-4 ${
              isDominant
                ? "border-brand-primary bg-brand-accent/25"
                : "border-border bg-surface"
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-sm font-bold text-text-primary">{meta.label}</h3>
              {isDominant ? (
                <span className="rounded bg-brand-primary px-2 py-0.5 text-[11px] font-semibold text-white dark:text-background">
                  Dominant
                </span>
              ) : null}
            </div>

            <p className="mt-2 text-2xl font-bold text-text-primary">
              {item.concentration}{" "}
              <span className="text-xs font-medium text-text-secondary">{item.unit}</span>
            </p>

            <div className="mt-2 flex items-center justify-between text-xs text-text-secondary">
              <span>{item.averaging_period_hours}h avg window</span>
              <span>
                {stdLabel} sub-index:{" "}
                <strong className="text-text-primary">
                  {item.sub_index !== null ? item.sub_index : "N/A"}
                </strong>
              </span>
            </div>

            <p className="mt-2 text-xs text-text-secondary">{meta.description}</p>
          </article>
        );
      })}
    </div>
  );
}
