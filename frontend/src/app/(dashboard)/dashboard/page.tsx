import Link from "next/link";
import { DashboardAqiSnapshot } from "@/features/air-quality/dashboard-aqi-snapshot";

const DASHBOARD_MODULES = [
  { title: "Current Air Quality", href: "/dashboard/air-quality", summary: "Standard-isolated AQI, pollutant breakdown, and data freshness provenance." },
  { title: "AirWise Copilot", href: "/dashboard/assistant", summary: "Controlled 12-tool GenAI assistant with RAG citations and SSE streaming." },
  { title: "Daily Routine Planner", href: "/dashboard/routine-planner", summary: "Morning-to-Night smog-aware schedule prioritizing exposure safety." },
  { title: "Indoor Air Guidance", href: "/dashboard/indoor-air", summary: "HEPA CADR sizing, ventilation timing, and source-control recommendations." },
  { title: "Sustainable Transport", href: "/dashboard/transport", summary: "Compare commute exposure alongside passenger-km CO2e estimates." },
  { title: "Impact Tracker", href: "/dashboard/impact", summary: "Track completed actions and transparent avoided-emissions estimates." },
  { title: "Smart Alerts", href: "/dashboard/alerts", summary: "Threshold, forecast, and clean-window alerts with quiet-hour controls." },
  { title: "Community Initiatives", href: "/dashboard/community", summary: "Neighborhood challenges and privacy-preserving aggregate metrics." },
] as const;

export default function DashboardOverviewPage() {
  return (
    <main id="main-content" className="mx-auto max-w-7xl px-6 py-10">
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">AirWise Environmental Dashboard</h1>
          <p className="text-sm text-text-secondary">
            Select a city or saved location to inspect verified air quality and personalized guidance.
          </p>
        </div>
        <div className="flex items-center gap-4 text-sm font-medium">
          <Link href="/dashboard/settings" className="text-brand-primary underline">
            Account &amp; Locations
          </Link>
          <Link href="/" className="text-brand-primary underline">
            Back to Overview
          </Link>
        </div>
      </div>

      <DashboardAqiSnapshot />

      <section aria-label="Dashboard modules" className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {DASHBOARD_MODULES.map((mod) => (
          <Link
            key={mod.href}
            href={mod.href}
            className="rounded-card border border-border bg-surface p-5 shadow-sm transition-colors hover:border-brand-primary"
          >
            <h2 className="text-base font-semibold text-text-primary">{mod.title}</h2>
            <p className="mt-2 text-sm text-text-secondary">{mod.summary}</p>
          </Link>
        ))}
      </section>
    </main>
  );
}
