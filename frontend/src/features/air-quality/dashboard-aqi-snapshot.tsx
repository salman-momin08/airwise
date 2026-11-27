"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AQIBadge } from "@/components/air-quality/aqi-badge";
import { ProvenanceBanner } from "@/components/air-quality/provenance-banner";
import { airQualityApi } from "@/lib/api/air-quality";
import { useLocationStore } from "@/stores/location-store";

export function DashboardAqiSnapshot() {
  const city = useLocationStore((s) => s.selectedCity);
  const standard = useLocationStore((s) => s.aqiStandard);

  const currentQuery = useQuery({
    queryKey: ["air-quality", "current", city, standard],
    queryFn: () => airQualityApi.getCurrent(city, standard),
  });

  if (currentQuery.isLoading) {
    return (
      <div
        aria-busy="true"
        className="mb-8 h-36 animate-pulse rounded-card border border-border bg-surface p-6"
      />
    );
  }

  const current = currentQuery.data?.data;
  if (!current) {
    return null;
  }

  return (
    <section
      aria-label="Active location air quality snapshot"
      className="mb-8 rounded-card border border-border bg-surface p-6 shadow-sm"
    >
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-brand-primary">
            Active Snapshot · {current.city}
          </p>
          <p className="mt-1 text-sm text-text-primary">{current.precaution_summary}</p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <AQIBadge
            standard={current.standard}
            aqi={current.aqi}
            category={current.category}
          />
          <Link
            href="/dashboard/air-quality"
            className="rounded-lg bg-brand-primary px-3 py-1.5 text-xs font-semibold text-white dark:text-background"
          >
            Inspect Trends &amp; Map
          </Link>
        </div>
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
    </section>
  );
}
