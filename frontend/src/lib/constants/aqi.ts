/**
 * India NAQI and US EPA category metadata, accessible badge palettes, and labels.
 */

import type { AQIStandard } from "@/types/api";

export interface AQISeverityStyle {
  standardLabel: string;
  categoryLabel: string;
  badgeClasses: string;
  severitySymbol: string;
}

const INDIA_NAQI_STYLES: Record<string, Omit<AQISeverityStyle, "standardLabel">> = {
  Good: {
    categoryLabel: "Good",
    badgeClasses: "bg-emerald-100 text-emerald-950 border-emerald-400",
    severitySymbol: "●",
  },
  Satisfactory: {
    categoryLabel: "Satisfactory",
    badgeClasses: "bg-lime-100 text-lime-950 border-lime-500",
    severitySymbol: "◐",
  },
  Moderate: {
    categoryLabel: "Moderate",
    badgeClasses: "bg-amber-100 text-amber-950 border-amber-500",
    severitySymbol: "▲",
  },
  Poor: {
    categoryLabel: "Poor",
    badgeClasses: "bg-orange-100 text-orange-950 border-orange-500",
    severitySymbol: "◆",
  },
  "Very Poor": {
    categoryLabel: "Very Poor",
    badgeClasses: "bg-red-100 text-red-950 border-red-500",
    severitySymbol: "■",
  },
  Severe: {
    categoryLabel: "Severe",
    badgeClasses: "bg-rose-200 text-rose-950 border-rose-700",
    severitySymbol: "⬢",
  },
};

const US_EPA_STYLES: Record<string, Omit<AQISeverityStyle, "standardLabel">> = {
  Good: {
    categoryLabel: "Good",
    badgeClasses: "bg-emerald-100 text-emerald-950 border-emerald-400",
    severitySymbol: "●",
  },
  Moderate: {
    categoryLabel: "Moderate",
    badgeClasses: "bg-yellow-100 text-yellow-950 border-yellow-500",
    severitySymbol: "◐",
  },
  "Unhealthy for Sensitive Groups": {
    categoryLabel: "Unhealthy for Sensitive Groups",
    badgeClasses: "bg-amber-100 text-amber-950 border-amber-600",
    severitySymbol: "▲",
  },
  Unhealthy: {
    categoryLabel: "Unhealthy",
    badgeClasses: "bg-red-100 text-red-950 border-red-500",
    severitySymbol: "◆",
  },
  "Very Unhealthy": {
    categoryLabel: "Very Unhealthy",
    badgeClasses: "bg-purple-100 text-purple-950 border-purple-600",
    severitySymbol: "■",
  },
  Hazardous: {
    categoryLabel: "Hazardous",
    badgeClasses: "bg-rose-200 text-rose-950 border-rose-800",
    severitySymbol: "⬢",
  },
};

export function describeAQISeverity(
  standard: AQIStandard,
  category: string | null,
): AQISeverityStyle {
  const standardLabel = standard === "india_naqi" ? "India NAQI" : "US EPA AQI";
  if (!category) {
    return {
      standardLabel,
      categoryLabel: "Unavailable",
      badgeClasses: "bg-slate-100 text-slate-800 border-slate-400",
      severitySymbol: "○",
    };
  }

  const lookup = standard === "india_naqi" ? INDIA_NAQI_STYLES : US_EPA_STYLES;
  const match = lookup[category];
  if (!match) {
    return {
      standardLabel,
      categoryLabel: category,
      badgeClasses: "bg-slate-100 text-slate-800 border-slate-400",
      severitySymbol: "○",
    };
  }
  return { standardLabel, ...match };
}
