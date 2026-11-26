import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SmartAlertsWorkspace } from "@/features/alerts/smart-alerts-workspace";
import { CommunityHubWorkspace } from "@/features/community/community-hub-workspace";
import { alertsCommunityApi } from "@/lib/api/alerts-community";
import { identityApi } from "@/lib/api/identity";

vi.mock("@/lib/api/alerts-community", () => ({
  alertsCommunityApi: {
    listAlertRules: vi.fn(),
    createAlertRule: vi.fn(),
    updateAlertRule: vi.fn(),
    deleteAlertRule: vi.fn(),
    evaluateMyAlerts: vi.fn(),
    unsubscribeAllAlerts: vi.fn(),
    listNotifications: vi.fn(),
    markNotificationRead: vi.fn(),
    markAllNotificationsRead: vi.fn(),
    listCommunities: vi.fn(),
    getCommunityDetail: vi.fn(),
    createCommunity: vi.fn(),
    joinCommunity: vi.fn(),
    leaveCommunity: vi.fn(),
    listInitiatives: vi.fn(),
    createInitiative: vi.fn(),
    logParticipation: vi.fn(),
    submitAbuseReport: vi.fn(),
    listModerationReports: vi.fn(),
    resolveModerationReport: vi.fn(),
  },
}));

vi.mock("@/lib/api/identity", () => ({
  identityApi: {
    getMePrincipal: vi.fn(),
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

describe("Phase 6 Smart Alerts & Privacy-Preserving Community UI", () => {
  it("renders quiet-hour suppressed delivery statuses and supports one-click opt-out", async () => {
    vi.mocked(alertsCommunityApi.listAlertRules).mockResolvedValue({
      meta: { request_id: "r1", timestamp: "2026-11-26T12:00:00Z" },
      data: [
        {
          id: "44444444-4444-4444-8444-444444444444",
          location_id: null,
          city: "Delhi",
          alert_type: "aqi_threshold",
          aqi_standard: "india_naqi",
          threshold_value: 200,
          channels: ["in_app", "email"],
          quiet_hours_start: "22:00",
          quiet_hours_end: "07:00",
          cooldown_minutes: 180,
          timezone: "Asia/Kolkata",
          is_enabled: true,
          last_triggered_at: null,
          created_at: "2026-11-26T12:00:00Z",
        },
      ],
    });
    vi.mocked(alertsCommunityApi.listNotifications).mockResolvedValue({
      meta: { request_id: "r2", timestamp: "2026-11-26T12:00:00Z" },
      data: [
        {
          id: "55555555-5555-4555-8555-555555555555",
          alert_rule_id: "44444444-4444-4444-8444-444444444444",
          title: "Delhi India NAQI AQI 340 Breached Threshold",
          body: "Avoid prolonged outdoor exertion.",
          severity: "critical",
          dedup_key: "alert:test",
          read_at: null,
          created_at: "2026-11-26T20:00:00Z",
          deliveries: [
            {
              id: "66666666-6666-4666-8666-666666666666",
              channel: "email",
              status: "suppressed_quiet_hours",
              provider_message_id: null,
              attempt_count: 1,
              delivered_at: null,
            },
          ],
        },
      ],
    });
    vi.mocked(alertsCommunityApi.unsubscribeAllAlerts).mockResolvedValue({
      meta: { request_id: "r3", timestamp: "2026-11-26T12:01:00Z" },
      data: { disabled_rules_count: 1 },
    });

    renderWithQuery(<SmartAlertsWorkspace />);
    expect(await screen.findByText(/Quiet hours: 22:00–07:00/)).toBeTruthy();
    expect(await screen.findByText("suppressed_quiet_hours")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "One-Click Opt-Out All" }));
    await waitFor(() => expect(alertsCommunityApi.unsubscribeAllAlerts).toHaveBeenCalledTimes(1));
  });

  it("enforces privacy-by-default display consent and zero synthetic community data", async () => {
    vi.mocked(identityApi.getMePrincipal).mockResolvedValue({
      meta: { request_id: "p1", timestamp: "2026-11-26T12:00:00Z" },
      data: {
        user_id: "77777777-7777-4777-8777-777777777777",
        role: "user",
        is_email_verified: true,
        preferred_aqi_standard: "india_naqi",
      },
    });
    vi.mocked(alertsCommunityApi.listCommunities).mockResolvedValue({
      meta: { request_id: "c1", timestamp: "2026-11-26T12:00:00Z" },
      data: [
        {
          id: "88888888-8888-4888-8888-888888888888",
          slug: "indiranagar-clean-commute",
          name: "Indiranagar Clean Commute",
          city: "Bengaluru",
          coarse_boundary_label: "East Bengaluru · Metro Corridor",
          description: "Voluntary clean commute circle.",
          member_count: 4,
          active_initiatives_count: 1,
          is_current_user_member: false,
          current_user_public_display_consent: false,
          created_at: "2026-11-26T12:00:00Z",
        },
      ],
    });
    vi.mocked(alertsCommunityApi.getCommunityDetail).mockResolvedValue({
      meta: { request_id: "c2", timestamp: "2026-11-26T12:00:00Z" },
      data: {
        id: "88888888-8888-4888-8888-888888888888",
        slug: "indiranagar-clean-commute",
        name: "Indiranagar Clean Commute",
        city: "Bengaluru",
        coarse_boundary_label: "East Bengaluru · Metro Corridor",
        description: "Voluntary clean commute circle.",
        moderation_policy: "Coarse boundaries only.",
        member_count: 4,
        active_initiatives_count: 1,
        is_current_user_member: false,
        current_user_public_display_consent: false,
        total_self_reported_actions: 9,
        total_estimated_avoided_co2e_kg: 6.3,
        consented_member_display_names: [],
        privacy_and_methodology_notice: "Privacy-preserving aggregate metrics.",
        created_at: "2026-11-26T12:00:00Z",
      },
    });
    vi.mocked(alertsCommunityApi.listInitiatives).mockResolvedValue({
      meta: { request_id: "c3", timestamp: "2026-11-26T12:00:00Z" },
      data: [],
    });

    renderWithQuery(<CommunityHubWorkspace />);
    expect(await screen.findByText(/East Bengaluru · Metro Corridor/)).toBeTruthy();
    expect(
      await screen.findByText(/Individual member names are private by default/),
    ).toBeTruthy();

    const consentCheckbox = screen.getByRole("checkbox", {
      name: /Optional: Show my display name/i,
    }) as HTMLInputElement;
    expect(consentCheckbox.checked).toBe(false);
  });
});
