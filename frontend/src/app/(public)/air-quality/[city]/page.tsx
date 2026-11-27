import Link from "next/link";
import { AirQualityWorkspace } from "@/features/air-quality/air-quality-workspace";

interface CityAirQualityPageProps {
  params: Promise<{ city: string }>;
}

function formatCitySlug(slug: string): string {
  const decoded = decodeURIComponent(slug).replace(/-/g, " ").trim();
  if (!decoded) return "Delhi";
  return decoded
    .split(" ")
    .map((part) => (part ? part.charAt(0).toUpperCase() + part.slice(1).toLowerCase() : ""))
    .join(" ");
}

export default async function CityAirQualityPage({ params }: CityAirQualityPageProps) {
  const { city } = await params;
  const formattedCity = formatCitySlug(city);

  return (
    <main id="main-content" className="mx-auto max-w-6xl px-6 py-10">
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4 border-b border-border pb-5">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-brand-primary">
            Public City Monitor
          </p>
          <h1 className="mt-1 text-2xl font-bold text-text-primary">
            {formattedCity} Air Quality &amp; Smog Outlook
          </h1>
          <p className="mt-1 text-sm text-text-secondary">
            Verified station measurements, dominant pollutant sub-indices, data freshness, and
            exposure-first precautions.
          </p>
        </div>
        <div className="flex items-center gap-4 text-sm font-medium">
          <Link href="/air-quality" className="text-brand-primary underline">
            All Cities
          </Link>
          <Link
            href="/register"
            className="rounded-lg bg-brand-primary px-4 py-2 font-semibold text-white dark:text-background"
          >
            Save Alerts &amp; Routines
          </Link>
        </div>
      </div>

      <AirQualityWorkspace initialCity={formattedCity} mode="public" />
    </main>
  );
}
