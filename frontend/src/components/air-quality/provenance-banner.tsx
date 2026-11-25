interface ProvenanceBannerProps {
  provider: string;
  sourceType: "station" | "model" | "unavailable";
  measuredAt: string | null;
  isStale: boolean;
  isDevelopmentFixture: boolean;
}

export function ProvenanceBanner({
  provider,
  sourceType,
  measuredAt,
  isStale,
  isDevelopmentFixture,
}: ProvenanceBannerProps) {
  const sourceLabel =
    sourceType === "station"
      ? "Physical Monitoring Station"
      : sourceType === "model"
        ? "Regional Atmospheric Model (Not street-level sensor)"
        : "Unavailable";

  return (
    <div className="space-y-2">
      {isDevelopmentFixture ? (
        <div
          role="status"
          className="rounded-lg border border-amber-500/60 bg-amber-100/80 px-4 py-2.5 text-xs font-medium text-amber-950 dark:bg-amber-900/30 dark:text-amber-100"
        >
          <strong>Development Synthetic Fixture Active:</strong> Displaying labeled development
          reference telemetry (`is_development_fixture: true`). Configure live{" "}
          <code>AIR_QUALITY_PROVIDER=openaq</code> credentials for real-world station readings.
        </div>
      ) : null}

      {isStale ? (
        <div
          role="alert"
          className="rounded-lg border border-orange-500/70 bg-orange-100/80 px-4 py-2.5 text-xs font-medium text-orange-950 dark:bg-orange-950/40 dark:text-orange-100"
        >
          <strong>Stale Reading Warning:</strong> Upstream monitoring feed is delayed or
          temporarily unreachable. Showing the most recent verified observation rather than
          inventing live values.
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-text-secondary">
        <span>
          Source: <strong className="text-text-primary">{provider}</strong> ({sourceLabel})
        </span>
        <span>·</span>
        <span>
          Measured:{" "}
          <strong className="text-text-primary">
            {measuredAt ? new Date(measuredAt).toLocaleString() : "Timestamp unavailable"}
          </strong>
        </span>
      </div>
    </div>
  );
}
