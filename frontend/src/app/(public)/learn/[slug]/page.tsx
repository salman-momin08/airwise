import Link from "next/link";
import { notFound } from "next/navigation";
import { LEARN_ARTICLES } from "@/lib/constants/learn-articles";

interface LearnArticlePageProps {
  params: Promise<{ slug: string }>;
}

export default async function RoutePage({ params }: LearnArticlePageProps) {
  const { slug } = await params;
  const article = LEARN_ARTICLES.find((item) => item.slug === slug);
  if (!article) {
    notFound();
  }

  return (
    <main id="main-content" className="mx-auto max-w-4xl px-6 py-10">
      <Link href="/learn" className="text-xs font-semibold text-brand-primary underline">
        ← Back to Learning Hub
      </Link>
      <h1 className="mt-4 text-2xl font-bold text-text-primary sm:text-3xl">{article.title}</h1>
      <p className="mt-2 text-sm text-text-secondary">{article.summary}</p>

      <section className="mt-6 rounded-card border border-border bg-surface p-6">
        <h2 className="text-base font-semibold text-text-primary">Key Takeaways</h2>
        <ul className="mt-3 list-inside list-disc space-y-1.5 text-sm text-text-secondary">
          {article.keyTakeaways.map((point, idx) => (
            <li key={idx}>{point}</li>
          ))}
        </ul>
      </section>

      <div className="mt-6 space-y-4 text-sm leading-relaxed text-text-primary">
        {article.bodyParagraphs.map((para, idx) => (
          <p key={idx}>{para}</p>
        ))}
      </div>

      <section className="mt-8 rounded-card border border-border bg-surface p-5 text-xs">
        <h2 className="font-semibold text-text-primary">Official Public-Health References</h2>
        <ul className="mt-2 space-y-1.5 text-text-secondary">
          {article.officialReferences.map((ref) => (
            <li key={ref.url}>
              <a
                href={ref.url}
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-brand-primary underline"
              >
                {ref.title}
              </a>{" "}
              ({ref.publisher})
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
