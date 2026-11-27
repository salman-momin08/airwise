/**
 * Sanitized structured Copilot guidance card displaying verified telemetry, citations, and safety warnings.
 */

import { AQIBadge } from "@/components/air-quality/aqi-badge";
import { ProvenanceBanner } from "@/components/air-quality/provenance-banner";
import type { AssistantGuidance } from "@/types/assistant";

const TRUSTED_CITATION_HOSTS = new Set([
  "www.who.int",
  "www.epa.gov",
  "cpcb.nic.in",
  "ncdc.mohfw.gov.in",
]);

function hasDefaultHttpsPort(url: URL): boolean {
  return !url.port || url.port === "443";
}

export function trustedCitationUrl(value: string): string | null {
  try {
    const url = new URL(value);
    const isAllowed =
      url.protocol === "https:" &&
      TRUSTED_CITATION_HOSTS.has(url.hostname) &&
      !url.username &&
      !url.password &&
      hasDefaultHttpsPort(url);
    return isAllowed ? url.href : null;
  } catch {
    return null;
  }
}

function GuidanceReferenceList({
  references,
}: {
  references: AssistantGuidance["evidence_references"];
}) {
  if (references.length === 0) {
    return <p>No trusted reference documents were retrieved for this response.</p>;
  }
  return (
    <ul className="space-y-2">
      {references.map((reference) => {
        const href = trustedCitationUrl(reference.source_url);
        const reviewedDate = new Date(reference.last_reviewed_date).toLocaleDateString();
        return (
          <li key={reference.document_id}>
            {href ? (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-brand-primary underline"
              >
                {reference.title}
              </a>
            ) : (
              <span>{reference.title} (source link unavailable)</span>
            )}
            <p>
              {reference.publisher}; reviewed {reviewedDate}
            </p>
            {reference.freshness_note ? <p role="note">{reference.freshness_note}</p> : null}
          </li>
        );
      })}
    </ul>
  );
}

export function GuidanceCard({ guidance }: { guidance: AssistantGuidance }) {
  const conditions = guidance.environmental_conditions;
  const reading = conditions.reading;
  const impact = guidance.estimated_impact;
  const narrativeSections: Array<[string, string | null]> = [
    ["Recommended action", guidance.recommended_action],
    ["Why this helps", guidance.why_this_helps],
    ["Uncertainty and limitations", guidance.uncertainty_or_limitations],
    ["Safer alternative", guidance.safer_alternative],
  ];

  return (
    <article
      aria-label="Assistant guidance"
      className="space-y-4 rounded-card border border-border bg-surface p-5"
    >
      <h2 className="font-semibold text-text-primary">{guidance.situation_summary}</h2>

      <section aria-label="Environmental conditions" className="space-y-2">
        <h3 className="text-sm font-semibold">Environmental conditions</h3>
        <AQIBadge
          standard={conditions.standard}
          aqi={reading?.aqi ?? null}
          category={reading?.category ?? null}
        />
        <p className="text-sm">{conditions.notice}</p>
        {reading ? (
          <ProvenanceBanner
            provider={reading.provider}
            sourceType={reading.source_type}
            measuredAt={reading.measured_at}
            isStale={reading.is_stale}
            isDevelopmentFixture={reading.is_development_fixture}
          />
        ) : null}
      </section>

      {narrativeSections.map(
        ([label, content]) =>
          content && (
            <section key={label}>
              <h3 className="text-sm font-semibold">{label}</h3>
              <p className="whitespace-pre-wrap text-sm">{content}</p>
            </section>
          ),
      )}

      {impact ? (
        <section className="text-sm">
          <h3 className="font-semibold">Estimated impact (not a measurement)</h3>
          <p>
            {impact.estimated_difference} {impact.unit}; confidence: {impact.confidence}
          </p>
          <p>Method: {impact.methodology}</p>
          <ul className="list-inside list-disc">
            {impact.assumptions.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
          <p>Sources: {impact.source_references.join("; ")}</p>
        </section>
      ) : null}

      <section className="text-sm" aria-label="Evidence references">
        <h3 className="font-semibold">Verified reference documents</h3>
        <GuidanceReferenceList references={guidance.evidence_references} />
      </section>
    </article>
  );
}
