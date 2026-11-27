"use client";

/**
 * Root App Router error boundary rendering an accessible recovery view without leaking internals.
 */

import Link from "next/link";

export default function AppErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main id="main-content" className="mx-auto max-w-2xl px-6 py-16 text-text-primary">
      <div
        role="alert"
        className="space-y-4 rounded-card border border-border bg-surface p-8 shadow-sm"
      >
        <h1 className="text-2xl font-bold">Something went wrong</h1>
        <p className="text-sm text-text-secondary">
          AirWise encountered an unexpected display error. No environmental readings were guessed
          or fabricated.
        </p>
        {error.digest ? (
          <p className="font-mono text-xs text-text-secondary">Reference ID: {error.digest}</p>
        ) : null}
        <div className="flex flex-wrap gap-3 pt-2">
          <button
            type="button"
            onClick={reset}
            className="rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white dark:text-background"
          >
            Try again
          </button>
          <Link
            href="/air-quality"
            className="rounded-lg border border-text-secondary px-4 py-2 text-sm font-medium"
          >
            View public air quality
          </Link>
        </div>
      </div>
    </main>
  );
}
