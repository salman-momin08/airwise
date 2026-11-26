import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AssistantWorkspace } from "@/features/assistant/assistant-workspace";
import { assistantApi } from "@/lib/api/assistant";
import { identityApi } from "@/lib/api/identity";
import type { ChatResult } from "@/types/assistant";

vi.mock("@/lib/api/assistant", () => ({
  assistantApi: {
    listConversations: vi.fn(), messages: vi.fn(), deleteHistory: vi.fn(), stream: vi.fn(),
  },
}));
vi.mock("@/lib/api/identity", () => ({
  identityApi: { getUserProfileAndPreferences: vi.fn() },
}));

afterEach(() => { cleanup(); vi.clearAllMocks(); });

function renderWorkspace() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}><AssistantWorkspace /></QueryClientProvider>);
}

describe("Assistant workspace", () => {
  it("requires consent, streams a question, and renders the validated complete result", async () => {
    vi.mocked(identityApi.getUserProfileAndPreferences).mockResolvedValue({
      meta: { request_id: "test", timestamp: "2026-11-26T00:00:00Z" },
      data: {
        id: "11111111-1111-4111-8111-111111111111", email: "test@example.com",
        role: "user", is_email_verified: true, created_at: "2026-11-26T00:00:00Z",
        profile: {
          display_name: "Test", locale: "en", preferred_aqi_standard: "india_naqi",
          timezone: "UTC", updated_at: "2026-11-26T00:00:00Z",
        },
        preferences: {
          save_chat_history: false, age_category: null, household_size: null,
          has_vulnerable_members: null, work_schedule: null, school_schedule: null,
          commute_modes: [], cooking_type: null, ventilation_type: null,
          has_hepa_purifier: false, budget_tier: null, sustainability_goals: [],
          consent_updated_at: null,
        },
      },
    });
    vi.mocked(assistantApi.listConversations).mockResolvedValue({
      data: [], meta: { request_id: "test", timestamp: "2026-11-26T00:00:00Z" },
    });
    const result: ChatResult = {
      conversation_id: null, message_id: null, citations: [], tools_used: [],
      generation: {
        provider: "gemini", model_name: "test", prompt_version: "v1", token_usage: 12,
        latency_ms: 10, is_fallback: false, fallback_reason: null,
      },
      structured_response: {
        situation_summary: "Grounded pollution guidance.",
        environmental_conditions: {
          standard: "india_naqi", status: "unavailable", reading: null,
          notice: "Live air quality is unavailable.",
        },
        recommended_action: "Reduce indoor smoke sources.",
        why_this_helps: "Source control can reduce exposure.", estimated_impact: null,
        uncertainty_or_limitations: "Indoor air quality is unmeasured.", safer_alternative: null,
        evidence_references: [],
      },
    };
    vi.mocked(assistantApi.stream).mockImplementation(async (_, __, onEvent) => {
      onEvent({ event: "status", data: { request_id: "test", stage: "retrieval" } });
      onEvent({ event: "delta", data: { request_id: "test", content: result.structured_response.recommended_action } });
      return result;
    });
    renderWorkspace();
    const question = await screen.findByLabelText("Your environmental question");
    fireEvent.change(question, { target: { value: "Explain indoor smoke." } });
    fireEvent.click(screen.getByRole("button", { name: "Send question" }));
    expect(await screen.findByText("Please consent before sending a question to Gemini.")).toBeTruthy();
    expect(assistantApi.stream).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("checkbox", { name: /I agree to send/ }));
    fireEvent.click(screen.getByRole("button", { name: "Send question" }));
    expect(await screen.findByRole("article", { name: "Assistant guidance" })).toBeTruthy();
    expect(screen.getByText("Reduce indoor smoke sources.")).toBeTruthy();
    await waitFor(() => expect(assistantApi.stream).toHaveBeenCalledTimes(1));
    expect(vi.mocked(assistantApi.stream).mock.calls[0][0].ai_consent).toBe(true);
    expect(screen.getByText(/Chat history is/).textContent).toContain("not saved");
  });
});
