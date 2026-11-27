"use client";

/**
 * Secondary navigation bar across profile, locations, preferences, and privacy settings.
 */

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { identityApi } from "@/lib/api/identity";

const SETTINGS_LINKS = [
  { href: "/dashboard/settings", label: "Overview" },
  { href: "/dashboard/settings/profile", label: "Profile & Sessions" },
  { href: "/dashboard/settings/locations", label: "Saved Locations" },
  { href: "/dashboard/settings/preferences", label: "Household & Commute" },
  { href: "/dashboard/settings/privacy", label: "Privacy, Export & Erase" },
] as const;

export function SettingsSubnav() {
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: principalResponse } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => identityApi.getMePrincipal(),
  });

  const logoutMutation = useMutation({
    mutationFn: () => identityApi.logout(),
    onSuccess: () => {
      queryClient.clear();
      router.push("/login");
    },
  });

  const principal = principalResponse?.data;
  const isAuthenticated = Boolean(principal?.user_id && principal.role !== "guest");

  return (
    <div className="mb-8 border-b border-border pb-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <nav aria-label="Settings sections" className="flex flex-wrap gap-2">
          {SETTINGS_LINKS.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                  active
                    ? "bg-brand-primary text-white dark:text-background"
                    : "border border-border bg-surface text-text-primary hover:bg-brand-accent/40"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-3 text-sm">
          <Link href="/dashboard" className="font-medium text-brand-primary underline">
            Dashboard
          </Link>
          {isAuthenticated ? (
            <button
              type="button"
              onClick={() => logoutMutation.mutate()}
              disabled={logoutMutation.isPending}
              className="rounded-lg border border-border bg-surface px-3 py-1.5 font-medium text-text-primary hover:bg-brand-accent/30 disabled:opacity-60"
            >
              {logoutMutation.isPending ? "Signing out…" : "Sign out"}
            </button>
          ) : (
            <Link
              href="/login"
              className="rounded-lg bg-brand-primary px-3 py-1.5 font-medium text-white dark:text-background"
            >
              Sign in
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
