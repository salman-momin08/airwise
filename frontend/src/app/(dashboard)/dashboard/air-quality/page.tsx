import Link from "next/link";
import { AirQualityWorkspace } from "@/features/air-quality/air-quality-workspace";

export default function DashboardAirQualityPage() {
  return (
    <main id="main-content" className="mx-auto max-w-6xl px-6 py-10">
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4 border-b border-border pb-5">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">
            Detailed Air Quality, Trends &amp; Stations
          </h1>
          <p className="mt-1 text-sm text-text-secondary">
            24-hour, 7-day, and 30-day pollutant time series, hourly forecast strip, dispersion
            meteorology, and nearby station map.
          </p>
        </div>
        <div className="flex items-center gap-4 text-sm font-medium">
          <Link href="/dashboard/settings/locations" className="text-brand-primary underline">
            Manage Saved Locations
          </Link>
          <Link href="/dashboard" className="text-brand-primary underline">
            Dashboard Overview
          </Link>
        </div>
      </div>

      <AirQualityWorkspace mode="dashboard" />
    </main>
  );
}
