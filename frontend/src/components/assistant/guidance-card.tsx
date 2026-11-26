import { AQIBadge } from "@/components/air-quality/aqi-badge";
import { ProvenanceBanner } from "@/components/air-quality/provenance-banner";
import type { AssistantGuidance } from "@/types/assistant";

export function trustedCitationUrl(value: string): string | null {
  try {
    const url = new URL(value);
    const hosts = ["www.who.int", "www.epa.gov", "cpcb.nic.in", "ncdc.mohfw.gov.in"];
    return url.protocol === "https:" && hosts.includes(url.hostname) &&
      !url.username && !url.password && (!url.port || url.port === "443") ? url.href : null;
  } catch {
    return null;
  }
}

export function GuidanceCard({ guidance }: { guidance: AssistantGuidance }) {
  const conditions = guidance.environmental_conditions;
  const reading = conditions.reading;
  const impact = guidance.estimated_impact;
  return (
    <article aria-label="Assistant guidance" className="space-y-4 rounded-card border border-border bg-surface p-5">
      <h2 className="font-semibold text-text-primary">{guidance.situation_summary}</h2>
      <section aria-label="Environmental conditions" className="space-y-2">
        <h3 className="text-sm font-semibold">Environmental conditions</h3>
        <AQIBadge
          standard={conditions.standard}
          aqi={reading?.aqi ?? null}
          category={reading?.category ?? null}
        />
        <p className="text-sm">{conditions.notice}</p>
        {reading && <ProvenanceBanner
          provider={reading.provider} sourceType={reading.source_type}
          measuredAt={reading.measured_at} isStale={reading.is_stale}
          isDevelopmentFixture={reading.is_development_fixture}
        />}
      </section>
      {[
        ["Recommended action", guidance.recommended_action],
        ["Why this helps", guidance.why_this_helps],
        ["Uncertainty and limitations", guidance.uncertainty_or_limitations],
        ["Safer alternative", guidance.safer_alternative],
      ].map(([label, content]) => content && (
        <section key={label}>
          <h3 className="text-sm font-semibold">{label}</h3>
          <p className="whitespace-pre-wrap text-sm">{content}</p>
        </section>
      ))}
      {impact && <section className="text-sm">
        <h3 className="font-semibold">Estimated impact (not a measurement)</h3>
        <p>{impact.estimated_difference} {impact.unit}; confidence: {impact.confidence}</p>
        <p>Method: {impact.methodology}</p>
        <ul className="list-inside list-disc">{impact.assumptions.map((item, index) =>
          <li key={index}>{item}</li>)}</ul>
        <p>Sources: {impact.source_references.join("; ")}</p>
      </section>}
      <section className="text-sm" aria-label="Evidence references">
        <h3 className="font-semibold">Verified reference documents</h3>
        {guidance.evidence_references.length === 0
          ? <p>No trusted reference documents were retrieved for this response.</p>
          : <ul className="space-y-2">{guidance.evidence_references.map((reference) => {
            const href = trustedCitationUrl(reference.source_url);
            return <li key={reference.document_id}>
              {href ? <a href={href} target="_blank" rel="noopener noreferrer"
                className="font-medium text-brand-primary underline">{reference.title}</a>
                : <span>{reference.title} (source link unavailable)</span>}
              <p>{reference.publisher}; reviewed {new Date(reference.last_reviewed_date).toLocaleDateString()}</p>
              {reference.freshness_note && <p role="note">{reference.freshness_note}</p>}
            </li>;
          })}</ul>}
      </section>
    </article>
  );
}
