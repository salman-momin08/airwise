import { AQIBadge } from "@/components/air-quality/aqi-badge";
import type { AirQualityForecast } from "@/types/api";

interface ForecastStripProps {
  forecast: AirQualityForecast | null;
  isLoading: boolean;
  isError: boolean;
}

export function ForecastStrip({ forecast, isLoading, isError }: ForecastStripProps) {
  if (isLoading) {
    return (
      <div
        aria-busy="true"
        className="h-44 animate-pulse rounded-card border border-border bg-surface p-6"
      />
    );
  }

  if (isError || !forecast || forecast.points.length === 0) {
    return (
      <section className="rounded-card border border-border bg-surface p-6 text-sm text-text-secondary">
        <h2 className="text-lg font-semibold text-text-primary">24-Hour Pollution Forecast</h2>
        <p className="mt-2">
          Hourly forecast projections are currently unavailable for this location.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-card border border-border bg-surface p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold text-text-primary">
            24-Hour Pollution Forecast &amp; Safer Windows
          </h2>
          <p className="text-xs text-text-secondary">
            Modeled projections ({forecast.provider}) · Generated{" "}
            {new Date(forecast.generated_at).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {forecast.points.slice(0, 8).map((pt) => (
          <article
            key={pt.forecast_for}
            className={`rounded-card border p-3.5 ${
              pt.safer_outdoor_window
                ? "border-brand-secondary bg-brand-accent/30"
                : "border-border bg-background"
            }`}
          >
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-text-primary">
                {new Date(pt.forecast_for).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
              <span className="uppercase text-text-secondary">
                {pt.confidence_level} conf.
              </span>
            </div>

            <div className="mt-2">
              <AQIBadge
                standard={forecast.standard}
                aqi={pt.aqi}
                category={pt.category}
              />
            </div>

            <p className="mt-2 text-xs text-text-secondary">
              PM2.5: {pt.pm25_ug_m3 !== null ? `${pt.pm25_ug_m3} µg/m³` : "N/A"}
            </p>

            {pt.safer_outdoor_window ? (
              <p className="mt-1.5 text-xs font-semibold text-brand-secondary">
                ✓ Relatively lower exposure window
              </p>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}
