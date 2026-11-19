import { describeAQISeverity } from "@/lib/constants/aqi";
import type { AQIStandard } from "@/types/api";

interface AQIBadgeProps {
  standard: AQIStandard;
  aqi: number | null;
  category: string | null;
}

export function AQIBadge({ standard, aqi, category }: AQIBadgeProps) {
  const descriptor = describeAQISeverity(standard, category);

  return (
    <span
      role="status"
      aria-label={`${descriptor.standardLabel}: ${aqi ?? "Unavailable"} (${descriptor.categoryLabel})`}
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-semibold ${descriptor.badgeClasses}`}
    >
      <span aria-hidden="true">{descriptor.severitySymbol}</span>
      <span>{aqi !== null ? `AQI ${aqi}` : "AQI Unavailable"}</span>
      <span>·</span>
      <span>{descriptor.categoryLabel}</span>
      <span className="text-xs font-normal opacity-80">({descriptor.standardLabel})</span>
    </span>
  );
}
