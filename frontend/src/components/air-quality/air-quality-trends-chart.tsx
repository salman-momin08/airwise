"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { HistoricalAirQuality, HistoryPeriod } from "@/types/api";

const PERIOD_OPTIONS: { value: HistoryPeriod; label: string }[] = [
  { value: "24h", label: "24 Hours" },
  { value: "7d", label: "7 Days" },
  { value: "30d", label: "30 Days" },
];

interface AirQualityTrendsChartProps {
  history: HistoricalAirQuality | null;
  period: HistoryPeriod;
  onPeriodChange: (period: HistoryPeriod) => void;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}

interface TrendChartPoint {
  label: string;
  aqi: number | null;
  pm25: number | null;
}

function formatTrendPointLabel(timestamp: string, period: HistoryPeriod): string {
  const dt = new Date(timestamp);
  return period === "24h"
    ? dt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : dt.toLocaleDateString([], { month: "short", day: "numeric" });
}

function computeAqiRange(series: HistoricalAirQuality["series"]): {
  minAqi: number | null;
  maxAqi: number | null;
} {
  const validAqis = series
    .map((s) => s.aqi)
    .filter((val): val is number => val !== null);
  if (validAqis.length === 0) {
    return { minAqi: null, maxAqi: null };
  }
  return { minAqi: Math.min(...validAqis), maxAqi: Math.max(...validAqis) };
}

function TrendChartCanvas({
  chartData,
  stdLabel,
  period,
  minAqi,
  maxAqi,
}: {
  chartData: TrendChartPoint[];
  stdLabel: string;
  period: HistoryPeriod;
  minAqi: number | null;
  maxAqi: number | null;
}) {
  const srSummary =
    minAqi !== null && maxAqi !== null
      ? `${stdLabel} ${period} trend series with ${chartData.length} observations ranging from AQI ${minAqi} to ${maxAqi}. Missing intervals are left unplotted.`
      : `${stdLabel} ${period} trend series with ${chartData.length} time intervals; AQI sub-index unavailable.`;

  return (
    <div
      className="mt-6 h-72 w-full"
      role="region"
      aria-label={`${stdLabel} ${period} trend chart`}
    >
      <p className="sr-only">{srSummary}</p>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#DCE7E5" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Area
            type="monotone"
            dataKey="aqi"
            name={stdLabel}
            stroke="#087F8C"
            fill="#D5F2E3"
            strokeWidth={2}
            connectNulls={false}
          />
          <Area
            type="monotone"
            dataKey="pm25"
            name="PM2.5 (µg/m³)"
            stroke="#2D8A67"
            fill="transparent"
            strokeWidth={2}
            connectNulls={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function AirQualityTrendsChart({
  history,
  period,
  onPeriodChange,
  isLoading,
  isError,
  onRetry,
}: AirQualityTrendsChartProps) {
  const stdLabel = history?.standard === "us_epa" ? "US EPA AQI" : "India NAQI";
  const series = history?.series ?? [];
  const chartData: TrendChartPoint[] = series.map((pt) => ({
    label: formatTrendPointLabel(pt.timestamp, period),
    aqi: pt.aqi,
    pm25: pt.pm25_ug_m3,
  }));
  const { minAqi, maxAqi } = computeAqiRange(series);
  const subtitle =
    minAqi !== null && maxAqi !== null
      ? `Range over ${period}: AQI ${minAqi} – ${maxAqi} (PM2.5 µg/m³ overlaid)`
      : "Time-series pollutant history";

  return (
    <section className="rounded-card border border-border bg-surface p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-text-primary">
            Historical Air Quality Trends ({stdLabel})
          </h2>
          <p className="text-xs text-text-secondary">{subtitle}</p>
        </div>

        <div role="group" aria-label="Select trend window" className="flex gap-2">
          {PERIOD_OPTIONS.map((opt) => {
            const active = period === opt.value;
            return (
              <button
                key={opt.value}
                type="button"
                aria-pressed={active}
                onClick={() => onPeriodChange(opt.value)}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                  active
                    ? "bg-brand-primary text-white dark:text-background"
                    : "border border-border bg-background text-text-primary hover:bg-brand-accent/40"
                }`}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
      </div>

      {isLoading ? (
        <div
          aria-busy="true"
          className="mt-6 h-64 animate-pulse rounded-lg bg-border"
        />
      ) : isError ? (
        <div role="alert" className="mt-6 rounded-lg border border-border bg-background p-6 text-sm">
          <p className="text-text-primary">
            Historical trend series could not be loaded right now.
          </p>
          <button
            type="button"
            onClick={onRetry}
            className="mt-3 rounded-lg bg-brand-primary px-3 py-1.5 text-xs font-semibold text-white dark:text-background"
          >
            Retry
          </button>
        </div>
      ) : chartData.length === 0 ? (
        <p className="mt-6 rounded-lg border border-dashed border-border p-6 text-sm text-text-secondary">
          No verified historical observations available for this time range.
        </p>
      ) : (
        <TrendChartCanvas
          chartData={chartData}
          stdLabel={stdLabel}
          period={period}
          minAqi={minAqi}
          maxAqi={maxAqi}
        />
      )}
    </section>
  );
}
