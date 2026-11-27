import Link from "next/link";
import { AirQualityWorkspace } from "@/features/air-quality/air-quality-workspace";

export default function PublicAirQualityExplorerPage() {
  return (
    <main id="main-content" className="mx-auto max-w-6xl px-6 py-10">
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4 border-b border-border pb-5">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Public Air Quality Explorer</h1>
          <p className="mt-1 text-sm text-text-secondary">
            Browse verified city air quality measurements, 24h–30d trends, forecasts, and nearby
            stations with strict India NAQI and US EPA isolation.
          </p>
        </div>
        <div className="flex items-center gap-3 text-sm font-medium">
          <Link href="/" className="text-brand-primary underline">
            Home
          </Link>
          <Link
            href="/dashboard"
            className="rounded-lg bg-brand-primary px-4 py-2 font-semibold text-white dark:text-background"
          >
            Dashboard
          </Link>
        </div>
      </div>

      <AirQualityWorkspace mode="public" />
    </main>
  );
}