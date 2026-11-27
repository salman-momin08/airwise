"use client";

/**
 * Segment-scoped error boundary for `/admin/*` governance views.
 */

import Link from "next/link";

export default function AdminErrorBoundary({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main id="main-content" className="mx-auto max-w-3xl px-6 py-12 text-text-primary">
      <div role="alert" className="space-y-4 rounded-card border border-border bg-surface p-6">
        <h1 className="text-xl font-bold">Administration workspace error</h1>
        <p className="text-sm text-text-secondary">
          Unable to render this governance panel right now.
        </p>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={reset}
            className="rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white dark:text-background"
          >
            Retry panel
          </button>
          <Link
            href="/admin"
            className="rounded-lg border border-text-secondary px-4 py-2 text-sm font-medium"
          >
            Admin overview
          </Link>
        </div>
      </div>
    </main>
  );
}
