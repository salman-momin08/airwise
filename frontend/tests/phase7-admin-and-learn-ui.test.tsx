import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AdminOverviewWorkspace } from "@/features/admin/admin-overview-and-users";
import { adminApi } from "@/lib/api/admin";
import { ApiClientError } from "@/lib/api/client";
import { LEARN_ARTICLES } from "@/lib/constants/learn-articles";

vi.mock("@/lib/api/admin", () => ({
  adminApi: {
    getOverview: vi.fn(),
    listSystemSettings: vi.fn(),
    upsertSystemSetting: vi.fn(),
  },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function renderWithQuery(node: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

describe("Phase 7 Admin Console & Clean Air Learning Hub", () => {
  it("blocks unauthorized viewers cleanly and renders live operational counts for admins", async () => {
    vi.mocked(adminApi.getOverview).mockRejectedValueOnce(
      new ApiClientError("AUTH_FORBIDDEN", "Admin required", "req-403", 403),
    );
    renderWithQuery(<AdminOverviewWorkspace />);
    expect(
      await screen.findByText(/Administrator privileges are required/),
    ).toBeTruthy();

    cleanup();

    vi.mocked(adminApi.getOverview).mockResolvedValueOnce({
      meta: { request_id: "req-200", timestamp: "2026-11-26T12:00:00Z" },
      data: {
        active_users_count: 14,
        enabled_data_sources_count: 3,
        ingested_documents_count: 3,
        knowledge_chunks_count: 9,
        total_ai_generations: 25,
        ai_fallback_rate: 0.12,
        open_moderation_reports_count: 0,
        audit_log_entries_count: 42,
        active_aqi_provider_mode: "openaq",
        active_llm_provider: "gemini",
      },
    });
    vi.mocked(adminApi.listSystemSettings).mockResolvedValueOnce({
      meta: { request_id: "req-201", timestamp: "2026-11-26T12:00:00Z" },
      data: [],
    });

    renderWithQuery(<AdminOverviewWorkspace />);
    expect(await screen.findByText("14")).toBeTruthy();
    expect(await screen.findByText(/3 docs · 9 chunks/)).toBeTruthy();
    expect(await screen.findByText(/12.0%/)).toBeTruthy();
  });

  it("maintains verified HTTPS public-health citations across all Learning Hub articles", () => {
    expect(LEARN_ARTICLES.length).toBeGreaterThanOrEqual(4);
    for (const article of LEARN_ARTICLES) {
      expect(article.officialReferences.length).toBeGreaterThan(0);
      for (const ref of article.officialReferences) {
        expect(ref.url.startsWith("https://")).toBe(true);
      }
    }
  });
});
