"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { trustedCitationUrl } from "@/components/assistant/guidance-card";
import { ApiClientError } from "@/lib/api/client";
import { planningApi } from "@/lib/api/planning";
import { useLocationStore } from "@/stores/location-store";
import type {
  RecommendationCard,
  RecommendationFeedbackStatus,
  RecommendationPriority,
} from "@/types/planning";

const PRIORITY_BADGES: Record<
  RecommendationPriority,
  { symbol: string; label: string; classes: string }
> = {
  critical: {
    symbol: "▲",
    label: "Critical Exposure Priority",
    classes: "border-red-600/80 bg-red-100 text-red-950 dark:bg-red-950/60 dark:text-red-100",
  },
  high: {
    symbol: "◆",
    label: "High Priority",
    classes:
      "border-orange-600/80 bg-orange-100 text-orange-950 dark:bg-orange-950/60 dark:text-orange-100",
  },
  medium: {
    symbol: "●",
    label: "Medium Priority",
    classes:
      "border-brand-primary/70 bg-brand-accent/50 text-text-primary",
  },
  low: {
    symbol: "○",
    label: "Low Priority",
    classes: "border-border bg-surface text-text-secondary",
  },
};

const CATEGORY_LABELS: Record<RecommendationCard["category"], string> = {
  routine: "Daily Routine",
  transport: "Transport & Mobility",
  indoor_air: "Indoor Air Protection",
  household_sustainability: "Household Energy",
  community: "Community Action",
};

export function TodayRecommendationsPanel() {
  const queryClient = useQueryClient();
  const city = useLocationStore((s) => s.selectedCity);
  const standard = useLocationStore((s) => s.aqiStandard);
  const [useAiPhrasing, setUseAiPhrasing] = useState(false);

  const todayQuery = useQuery({
    queryKey: ["recommendations", "today"],
    queryFn: () => planningApi.getTodayRecommendations(),
    retry: false,
  });

  const generateMutation = useMutation({
    mutationFn: () =>
      planningApi.generateRecommendations({
        city,
        standard,
        commute_distance_km: 10,
        use_ai_phrasing: useAiPhrasing,
        ai_consent: useAiPhrasing,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["recommendations", "today"] });
    },
  });

  const feedbackMutation = useMutation({
    mutationFn: (vars: { id: string; status: RecommendationFeedbackStatus }) =>
      planningApi.submitRecommendationFeedback(vars.id, { status: vars.status }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["recommendations", "today"] });
    },
  });

  if (todayQuery.isLoading) {
    return (
      <div
        aria-busy="true"
        className="mb-8 h-48 animate-pulse rounded-card border border-border bg-surface p-6"
      />
    );
  }

  if (todayQuery.isError) {
    const unauth =
      todayQuery.error instanceof ApiClientError && todayQuery.error.status === 401;
    return (
      <section
        aria-label="Personalized recommendations"
        className="mb-8 rounded-card border border-border bg-surface p-6 text-sm"
      >
        <h2 className="text-lg font-semibold text-text-primary">
          Today&apos;s Exposure-First Recommendations
        </h2>
        {unauth ? (
          <p className="mt-2 text-text-secondary">
            <Link href="/login" className="font-semibold text-brand-primary underline">
              Sign in
            </Link>{" "}
            to generate personalized recommendations across routine, transport, indoor air,
            household energy, and community categories.
          </p>
        ) : (
          <div role="alert" className="mt-2 space-y-2">
            <p>Unable to load recommendations right now.</p>
            <button
              type="button"
              onClick={() => void todayQuery.refetch()}
              className="rounded border border-text-secondary px-3 py-1.5 font-medium"
            >
              Retry
            </button>
          </div>
        )}
      </section>
    );
  }

  const cards = todayQuery.data?.data ?? [];

  return (
    <section
      aria-label="Today's prioritized recommendations"
      className="mb-8 space-y-4 rounded-card border border-border bg-surface p-6 shadow-sm"
    >
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-text-primary">
            Today&apos;s Hybrid Recommendations ({city})
          </h2>
          <p className="text-xs text-text-secondary">
            Deterministic safety overrides always take precedence over emissions or convenience.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-text-secondary">
            <input
              type="checkbox"
              checked={useAiPhrasing}
              onChange={(e) => setUseAiPhrasing(e.target.checked)}
            />
            Consent to optional Gemini plain-language phrasing
          </label>
          <button
            type="button"
            disabled={generateMutation.isPending}
            onClick={() => generateMutation.mutate()}
            className="rounded bg-brand-primary px-4 py-2 text-xs font-semibold text-white dark:text-background disabled:opacity-60"
          >
            {generateMutation.isPending
              ? "Generating..."
              : cards.length > 0
                ? "Refresh Recommendations"
                : "Generate Today's 5 Cards"}
          </button>
        </div>
      </div>

      {generateMutation.isError ? (
        <p role="alert" className="text-sm text-red-700 dark:text-red-300">
          {generateMutation.error instanceof Error
            ? generateMutation.error.message
            : "Could not generate recommendations."}
        </p>
      ) : null}

      {cards.length === 0 ? (
        <p className="rounded-lg border border-border p-4 text-sm text-text-secondary">
          No active recommendation cards generated yet for today. Select{" "}
          <strong>Generate Today&apos;s 5 Cards</strong> to evaluate {city} ({standard.toUpperCase()}).
        </p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {cards.map((card) => {
            const pBadge = PRIORITY_BADGES[card.priority];
            return (
              <article
                key={card.id}
                className="flex flex-col justify-between space-y-3 rounded-lg border border-border p-4"
              >
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                    <span className="font-semibold uppercase tracking-wide text-brand-primary">
                      {CATEGORY_LABELS[card.category]}
                    </span>
                    <span
                      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 font-semibold ${pBadge.classes}`}
                    >
                      <span aria-hidden="true">{pBadge.symbol}</span>
                      <span>{pBadge.label}</span>
                    </span>
                  </div>

                  <h3 className="text-base font-semibold text-text-primary">{card.title}</h3>
                  <p className="text-sm text-text-secondary">{card.reason}</p>

                  <ul className="list-inside list-disc space-y-1 text-xs text-text-primary">
                    {card.action_steps.map((step, idx) => (
                      <li key={idx}>{step}</li>
                    ))}
                  </ul>

                  {card.impact_estimate ? (
                    <p className="rounded border border-border bg-background px-3 py-2 text-xs text-text-secondary">
                      <strong className="text-text-primary">Deterministic Estimate:</strong>{" "}
                      {card.impact_estimate.estimated_difference} {card.impact_estimate.unit} (
                      {card.impact_estimate.methodology}, confidence:{" "}
                      {card.impact_estimate.confidence})
                    </p>
                  ) : null}

                  <p className="text-xs text-text-secondary">{card.uncertainty_note}</p>

                  {card.evidence_references.length > 0 ? (
                    <div className="text-xs text-text-secondary">
                      <strong className="text-text-primary">Sources: </strong>
                      {card.evidence_references.map((ref, i) => {
                        const safeHref = trustedCitationUrl(ref.source_url);
                        return (
                          <span key={ref.document_id}>
                            {i > 0 ? " · " : ""}
                            {safeHref ? (
                              <a
                                href={safeHref}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-brand-primary underline"
                              >
                                {ref.publisher}
                              </a>
                            ) : (
                              <span>{ref.publisher}</span>
                            )}
                          </span>
                        );
                      })}
                    </div>
                  ) : null}
                </div>

                <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3 text-xs">
                  <span className="text-text-secondary">
                    {card.latest_feedback
                      ? `Recorded: ${card.latest_feedback.replace("_", " ")}`
                      : "Was this actionable?"}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {(
                      ["completed", "helpful", "not_relevant", "dismissed"] as const
                    ).map((fbStatus) => (
                      <button
                        key={fbStatus}
                        type="button"
                        disabled={feedbackMutation.isPending}
                        onClick={() =>
                          feedbackMutation.mutate({ id: card.id, status: fbStatus })
                        }
                        className={`rounded border px-2 py-1 capitalize ${
                          card.latest_feedback === fbStatus
                            ? "border-brand-primary bg-brand-accent/60 font-semibold text-text-primary"
                            : "border-text-secondary text-text-primary"
                        }`}
                      >
                        {fbStatus.replace("_", " ")}
                      </button>
                    ))}
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
