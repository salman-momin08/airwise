/**
 * Secondary navigation bar across administrative governance workspaces.
 */

import Link from "next/link";

const ADMIN_LINKS = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/users", label: "Users" },
  { href: "/admin/data-sources", label: "Data Sources" },
  { href: "/admin/knowledge-base", label: "Knowledge Base" },
  { href: "/admin/ai-monitoring", label: "AI Monitoring" },
  { href: "/admin/community", label: "Community Queue" },
  { href: "/admin/audit-logs", label: "Audit Logs" },
] as const;

export function AdminSubnav() {
  return (
    <nav
      aria-label="Administrator navigation"
      className="mt-4 flex flex-wrap gap-2 border-b border-border pb-4 text-xs font-semibold"
    >
      {ADMIN_LINKS.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          className="rounded border border-text-secondary bg-surface px-3 py-1.5 text-text-primary hover:border-brand-primary"
        >
          {item.label}
        </Link>
      ))}
      <Link
        href="/dashboard"
        className="ml-auto rounded border border-border px-3 py-1.5 text-brand-primary underline"
      >
        User Dashboard
      </Link>
    </nav>
  );
}
