import Link from "next/link";

export default function LandingPage() {
  return (
    <main id="main-content" className="mx-auto max-w-6xl px-6 py-16">
      <header className="mb-12 flex flex-wrap items-center justify-between gap-4 border-b border-border pb-6">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wider text-brand-primary">
            AirWise AI
          </p>
          <p className="text-xs text-text-secondary">
            Breathe Smarter. Live Cleaner. Act Together.
          </p>
        </div>
        <nav aria-label="Primary navigation" className="flex items-center gap-4 text-sm font-medium">
          <Link href="/dashboard" className="rounded-lg bg-brand-primary px-4 py-2 text-white">
            Open Dashboard
          </Link>
        </nav>
      </header>

      <section className="rounded-card border border-border bg-surface p-8 shadow-sm">
        <h1 className="max-w-3xl text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
          Evidence-grounded smog protection and low-emission daily planning for families and neighborhoods.
        </h1>
        <p className="mt-4 max-w-2xl text-base text-text-secondary">
          AirWise AI separates personal pollution exposure reduction, household &amp; commute emission
          estimates, and privacy-preserving community initiatives—backed by verified monitoring data
          and transparent environmental math.
        </p>

        <div className="mt-8 grid gap-6 sm:grid-cols-3">
          <article className="rounded-card border border-border p-5">
            <h2 className="font-semibold text-text-primary">1. Personal Exposure First</h2>
            <p className="mt-2 text-sm text-text-secondary">
              Standard-isolated India NAQI &amp; US EPA telemetry with conservative guidance for
              children, commuters, and older adults.
            </p>
          </article>
          <article className="rounded-card border border-border p-5">
            <h2 className="font-semibold text-text-primary">2. Transparent Impact Math</h2>
            <p className="mt-2 text-sm text-text-secondary">
              Deterministic passenger-km CO2e, kWh, and HEPA CADR/ACH calculators with explicit
              assumptions—never LLM guesswork.
            </p>
          </article>
          <article className="rounded-card border border-border p-5">
            <h2 className="font-semibold text-text-primary">3. Collective Local Action</h2>
            <p className="mt-2 text-sm text-text-secondary">
              Join neighborhood no-idling and clean-air awareness challenges without sharing exact
              household coordinates.
            </p>
          </article>
        </div>
      </section>
    </main>
  );
}
