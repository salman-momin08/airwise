import Link from "next/link";
import { LEARN_ARTICLES } from "@/lib/constants/learn-articles";

export default function RoutePage() {
  return (
    <main id="main-content" className="mx-auto max-w-5xl px-6 py-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Clean Air Learning Hub</h1>
          <p className="mt-2 text-sm text-text-secondary">
            Evidence-based guides on PM2.5, winter temperature inversions, HEPA filtration, and
            respiratory safety.
          </p>
        </div>
        <Link href="/air-quality" className="text-sm font-medium text-brand-primary underline">
          Check Public City AQI
        </Link>
      </div>

      <div className="mt-8 grid gap-5 sm:grid-cols-2">
        {LEARN_ARTICLES.map((article) => (
          <article
            key={article.slug}
            className="flex flex-col justify-between rounded-card border border-border bg-surface p-6 shadow-sm"
          >
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-brand-primary">
                {article.readingTimeMinutes} min read
              </p>
              <h2 className="mt-2 text-lg font-semibold text-text-primary">{article.title}</h2>
              <p className="mt-2 text-sm text-text-secondary">{article.summary}</p>
            </div>
            <Link
              href={`/learn/${article.slug}`}
              className="mt-4 inline-block text-sm font-semibold text-brand-primary underline"
            >
              Read Guide →
            </Link>
          </article>
        ))}
      </div>
    </main>
  );
}