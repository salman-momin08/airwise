"use client";

/**
 * Full-featured public and authenticated city air quality explorer workspace.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AQIBadge } from "@/components/air-quality/aqi-badge";
import { AirQualityTrendsChart } from "@/components/air-quality/air-quality-trends-chart";
import { ForecastStrip } from "@/components/air-quality/forecast-strip";
import { LocationStandardToolbar } from "@/components/air-quality/location-standard-toolbar";
import { PollutantBreakdownGrid } from "@/components/air-quality/pollutant-breakdown-grid";
import { ProvenanceBanner } from "@/components/air-quality/provenance-banner";
import { StationsMapPanel } from "@/components/air-quality/stations-map-panel";
import { WeatherContextCard } from "@/components/air-quality/weather-context-card";
import { airQualityApi } from "@/lib/api/air-quality";
import { ApiClientError } from "@/lib/api/client";
import { identityApi } from "@/lib/api/identity";
import { useLocationStore } from "@/stores/location-store";
import type { CurrentAirQuality, CurrentWeather, HistoryPeriod } from "@/types/api";

interface AirQualityWorkspaceProps {
  initialCity?: string;
  mode: "public" | "dashboard";
}

const CITY_SHORTCUTS = ["Delhi", "Bengaluru", "Mumbai", "Chennai", "Kolkata"] as const;

function CurrentConditionsGrid({
  current,
  isLoading,
  isError,
  error,
  onRetry,
  weather,
  weatherLoading,
  weatherError,
}: {
  current: CurrentAirQuality | undefined;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  onRetry: () => void;
  weather: CurrentWeather | null;
  weatherLoading: boolean;
  weatherError: boolean;
}) {
  if (isLoading) {
    return (
      <div
        aria-busy="true"
        className="h-56 animate-pulse rounded-card border border-border bg-surface p-6"
      />
    );
  }
  if (isError || !current) {
    const message =
      error instanceof ApiClientError
        ? error.message
        : "Current air quality readings could not be retrieved. AirWise AI never displays fabricated fallback numbers.";
    return (
      <section
        role="alert"
        className="rounded-card border border-red-400/50 bg-surface p-6 text-sm"
      >
        <h2 className="text-base font-bold text-text-primary">
          Air Quality Telemetry Unavailable
        </h2>
        <p className="mt-2 text-text-secondary">{message}</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 rounded-lg bg-brand-primary px-4 py-2 text-xs font-semibold text-white dark:text-background"
        >
          Retry live fetch
        </button>
      </section>
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <section className="rounded-card border border-border bg-surface p-6 shadow-sm lg:col-span-2">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-brand-primary">
              {current.city} · Precision: {current.location_precision}
            </p>
            <h2 className="mt-1 text-2xl font-bold text-text-primary">
              Current Outdoor Air Quality
            </h2>
          </div>
          <AQIBadge
            standard={current.standard}
            aqi={current.aqi}
            category={current.category}
          />
        </div>

        <div className="mt-4">
          <ProvenanceBanner
            provider={current.provider}
            sourceType={current.source_type}
            measuredAt={current.measured_at}
            isStale={current.is_stale}
            isDevelopmentFixture={current.is_development_fixture}
          />
        </div>

        {current.unavailable_reason ? (
          <p className="mt-4 rounded-lg border border-border bg-background p-3 text-xs text-text-secondary">
            {current.unavailable_reason}
          </p>
        ) : null}

        <div className="mt-5 rounded-lg border border-brand-primary/30 bg-brand-accent/30 p-4">
          <h3 className="text-xs font-bold uppercase tracking-wide text-brand-primary">
            Exposure-First Precaution Guidance
          </h3>
          <p className="mt-1 text-sm text-text-primary">{current.precaution_summary}</p>
        </div>
      </section>

      <WeatherContextCard
        weather={weather}
        isLoading={weatherLoading}
        isError={weatherError}
      />
    </div>
  );
}

function useDashboardPrimaryLocationSync({
  mode,
  initialCity,
  savedLocations,
  preferredStandard,
  setActiveCity,
  setStoreCity,
  setStandard,
}: {
  mode: "public" | "dashboard";
  initialCity: string | undefined;
  savedLocations: Array<{ city: string; is_primary: boolean }>;
  preferredStandard: CurrentAirQuality["standard"] | undefined;
  setActiveCity: (city: string) => void;
  setStoreCity: (city: string) => void;
  setStandard: (std: CurrentAirQuality["standard"]) => void;
}) {
  useEffect(() => {
    if (mode !== "dashboard" || initialCity) return;
    const primary = savedLocations.find((l) => l.is_primary);
    if (primary) {
      setActiveCity(primary.city);
      setStoreCity(primary.city);
    }
    if (preferredStandard) {
      setStandard(preferredStandard);
    }
  }, [
    mode,
    initialCity,
    savedLocations,
    preferredStandard,
    setActiveCity,
    setStoreCity,
    setStandard,
  ]);
}

function CityShortcutsNav({ visible }: { visible: boolean }) {
  if (!visible) return null;
  return (
    <nav aria-label="Direct city pages" className="flex flex-wrap items-center gap-2 text-xs">
      <span className="font-semibold text-text-secondary">Direct city monitors:</span>
      {CITY_SHORTCUTS.map((city) => (
        <Link
          key={city}
          href={`/air-quality/${city.toLowerCase()}`}
          className="rounded-full border border-border bg-surface px-3 py-1 font-medium text-brand-primary hover:bg-brand-accent/40"
        >
          {city}
        </Link>
      ))}
    </nav>
  );
}

function useAirQualityTelemetryQueries(
  activeCity: string,
  standard: CurrentAirQuality["standard"],
  period: HistoryPeriod,
) {
  const currentQuery = useQuery({
    queryKey: ["air-quality", "current", activeCity, standard],
    queryFn: () => airQualityApi.getCurrent(activeCity, standard),
  });
  const weatherQuery = useQuery({
    queryKey: ["weather", "current", activeCity],
    queryFn: () => airQualityApi.getCurrentWeather(activeCity),
  });
  const historyQuery = useQuery({
    queryKey: ["air-quality", "history", activeCity, standard, period],
    queryFn: () => airQualityApi.getHistory(activeCity, standard, period),
  });
  const forecastQuery = useQuery({
    queryKey: ["air-quality", "forecast", activeCity, standard],
    queryFn: () => airQualityApi.getForecast(activeCity, standard, 24),
  });
  const stationsQuery = useQuery({
    queryKey: ["air-quality", "stations", activeCity, standard],
    queryFn: () => airQualityApi.getStations(activeCity, standard, 35),
  });
  return {
    currentQuery,
    current: currentQuery.data ? currentQuery.data.data : undefined,
    weather: weatherQuery.data ? weatherQuery.data.data : null,
    weatherLoading: weatherQuery.isLoading,
    weatherError: weatherQuery.isError,
    history: historyQuery.data ? historyQuery.data.data : null,
    historyLoading: historyQuery.isLoading,
    historyError: historyQuery.isError,
    refetchHistory: () => void historyQuery.refetch(),
    forecast: forecastQuery.data ? forecastQuery.data.data : null,
    forecastLoading: forecastQuery.isLoading,
    forecastError: forecastQuery.isError,
    stations: stationsQuery.data ? stationsQuery.data.data : [],
    stationsLoading: stationsQuery.isLoading,
    stationsError: stationsQuery.isError,
  };
}

export function AirQualityWorkspace({ initialCity, mode }: AirQualityWorkspaceProps) {
  const storeCity = useLocationStore((s) => s.selectedCity);
  const setStoreCity = useLocationStore((s) => s.setSelectedCity);
  const standard = useLocationStore((s) => s.aqiStandard);
  const setStandard = useLocationStore((s) => s.setAqiStandard);

  const [activeCity, setActiveCity] = useState<string>(initialCity ?? storeCity);
  const [period, setPeriod] = useState<HistoryPeriod>("24h");

  useEffect(() => {
    if (initialCity) setActiveCity(initialCity);
  }, [initialCity]);

  const mePrincipalQuery = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => identityApi.getMePrincipal(),
    enabled: mode === "dashboard",
  });

  const principal = mePrincipalQuery.data?.data;
  const isSignedIn = Boolean(principal && principal.user_id && principal.role !== "guest");

  const savedLocationsQuery = useQuery({
    queryKey: ["locations", "saved"],
    queryFn: () => identityApi.listSavedLocations(),
    enabled: mode === "dashboard" && isSignedIn,
  });

  const savedLocations = savedLocationsQuery.data ? savedLocationsQuery.data.data : [];
  useDashboardPrimaryLocationSync({
    mode,
    initialCity,
    savedLocations,
    preferredStandard: principal?.preferred_aqi_standard,
    setActiveCity,
    setStoreCity,
    setStandard,
  });

  const telemetry = useAirQualityTelemetryQueries(activeCity, standard, period);

  return (
    <div className="space-y-8">
      <LocationStandardToolbar
        selectedCity={activeCity}
        onCityChange={(nextCity) => {
          setActiveCity(nextCity);
          setStoreCity(nextCity);
        }}
        standard={standard}
        onStandardChange={setStandard}
        savedLocations={savedLocations}
      />

      <CityShortcutsNav visible={mode === "public"} />

      <CurrentConditionsGrid
        current={telemetry.current}
        isLoading={telemetry.currentQuery.isLoading}
        isError={telemetry.currentQuery.isError}
        error={telemetry.currentQuery.error}
        onRetry={() => void telemetry.currentQuery.refetch()}
        weather={telemetry.weather}
        weatherLoading={telemetry.weatherLoading}
        weatherError={telemetry.weatherError}
      />

      {telemetry.current ? (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold text-text-primary">
            Normalized Pollutant Concentrations &amp; Sub-Indices
          </h2>
          <PollutantBreakdownGrid
            pollutants={telemetry.current.pollutants}
            dominantPollutant={telemetry.current.dominant_pollutant}
            standard={telemetry.current.standard}
          />
        </section>
      ) : null}

      <ForecastStrip
        forecast={telemetry.forecast}
        isLoading={telemetry.forecastLoading}
        isError={telemetry.forecastError}
      />

      <AirQualityTrendsChart
        history={telemetry.history}
        period={period}
        onPeriodChange={setPeriod}
        isLoading={telemetry.historyLoading}
        isError={telemetry.historyError}
        onRetry={telemetry.refetchHistory}
      />

      <StationsMapPanel
        stations={telemetry.stations}
        isLoading={telemetry.stationsLoading}
        isError={telemetry.stationsError}
      />
    </div>
  );
}
