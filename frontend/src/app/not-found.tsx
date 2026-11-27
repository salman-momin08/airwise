/**
 * Accessible 404 Not Found route shell with direct links to public AQI and dashboard views.
 */

import Link from "next/link";

export default function NotFoundPage() {
  return (
    <main id="main-content" className="mx-auto max-w-2xl px-6 py-16 text-text-primary">
      <section className="space-y-4 rounded-card border border-border bg-surface p-8 shadow-sm">
        <h1 className="text-2xl font-bold">Page not found</h1>
        <p className="text-sm text-text-secondary">
          The requested AirWise page does not exist or may have moved.
        </p>
        <div className="flex flex-wrap gap-3 pt-2">
          <Link
            href="/"
            className="rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white dark:text-background"
          >
            Go to home
          </Link>
          <Link
            href="/air-quality"
            className="rounded-lg border border-text-secondary px-4 py-2 text-sm font-medium"
          >
            Explore city air quality
          </Link>
        </div>
      </section>
    </main>
  );
}
