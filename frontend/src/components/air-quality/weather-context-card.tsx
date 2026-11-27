/**
 * Meteorological temperature, wind, humidity, and thermal-inversion dispersion card.
 */

import type { CurrentWeather } from "@/types/api";

interface WeatherContextCardProps {
  weather: CurrentWeather | null;
  isLoading: boolean;
  isError: boolean;
}

export function WeatherContextCard({
  weather,
  isLoading,
  isError,
}: WeatherContextCardProps) {
  if (isLoading) {
    return (
      <div
        aria-busy="true"
        className="h-44 animate-pulse rounded-card border border-border bg-surface p-5"
      />
    );
  }

  if (isError || !weather) {
    return (
      <section className="rounded-card border border-border bg-surface p-5 text-sm text-text-secondary">
        <h2 className="text-base font-semibold text-text-primary">
          Meteorological Dispersion Context
        </h2>
        <p className="mt-2">
          Current meteorological observations are temporarily unavailable. Dispersion conditions
          have not been estimated.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-card border border-border bg-surface p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-text-primary">
          Meteorology &amp; Smog Dispersion
        </h2>
        {weather.inversion_risk_flag ? (
          <span className="rounded-full border border-orange-500 bg-orange-100 px-3 py-0.5 text-xs font-semibold text-orange-950">
            ▲ Inversion Stagnation Risk
          </span>
        ) : (
          <span className="rounded-full border border-emerald-500 bg-emerald-100 px-3 py-0.5 text-xs font-semibold text-emerald-950">
            ● Normal Dispersion
          </span>
        )}
      </div>

      <dl className="mt-4 grid grid-cols-3 gap-3 text-center">
        <div className="rounded-lg border border-border bg-background p-3">
          <dt className="text-xs text-text-secondary">Temperature</dt>
          <dd className="mt-1 text-lg font-bold text-text-primary">
            {weather.temperature_c}°C
          </dd>
        </div>
        <div className="rounded-lg border border-border bg-background p-3">
          <dt className="text-xs text-text-secondary">Humidity</dt>
          <dd className="mt-1 text-lg font-bold text-text-primary">
            {weather.humidity_pct}%
          </dd>
        </div>
        <div className="rounded-lg border border-border bg-background p-3">
          <dt className="text-xs text-text-secondary">Wind Speed</dt>
          <dd className="mt-1 text-lg font-bold text-text-primary">
            {weather.wind_speed_mps} m/s
          </dd>
        </div>
      </dl>

      <p className="mt-3 text-xs text-text-secondary">{weather.dispersion_note}</p>
    </section>
  );
}
