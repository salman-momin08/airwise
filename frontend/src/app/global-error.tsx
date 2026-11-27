"use client";

/**
 * Top-level root layout error boundary fallback for Next.js App Router.
 */

export default function GlobalErrorBoundary({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#F7FAF9] px-6 py-16 text-[#172B32] antialiased">
        <main id="main-content" className="mx-auto max-w-xl rounded-2xl border p-8">
          <div role="alert" className="space-y-4">
            <h1 className="text-2xl font-bold">AirWise AI is temporarily unavailable</h1>
            <p className="text-sm">
              An unexpected application error occurred while rendering the layout.
            </p>
            <button
              type="button"
              onClick={reset}
              className="rounded-lg bg-[#087F8C] px-4 py-2 text-sm font-semibold text-white"
            >
              Reload view
            </button>
          </div>
        </main>
      </body>
    </html>
  );
}
