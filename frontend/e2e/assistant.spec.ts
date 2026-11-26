import { expect, test } from "@playwright/test";

test("consented Gemini chat displays only the validated response and provenance", async ({ page }) => {
  let submissions = 0;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/users/me")) {
      await route.fulfill({ json: { data: { preferences: { save_chat_history: false } } } });
    } else if (path.endsWith("/assistant/conversations")) {
      await route.fulfill({ json: { data: [] } });
    } else if (path.endsWith("/assistant/chat/stream")) {
      submissions++;
      const request: { ai_consent: boolean; message: string; standard: string } =
        route.request().postDataJSON();
      expect(request.ai_consent).toBe(true);
      expect(request.message).toBe("Explain indoor smoke.");
      expect(request.standard).toBe("india_naqi");
      const guidance = {
        situation_summary: "General protection guidance.",
        environmental_conditions: {
          standard: "india_naqi", status: "unavailable", reading: null,
          notice: "Verified live air quality is unavailable.",
        },
        recommended_action: "Reduce indoor smoke sources.",
        why_this_helps: "Source control can reduce exposure.",
        estimated_impact: null,
        uncertainty_or_limitations: "Indoor air quality is unmeasured.",
        safer_alternative: null,
        evidence_references: [],
      };
      const result = {
        request_id: "browser-test", conversation_id: null, message_id: null,
        structured_response: guidance, citations: [], tools_used: [],
        generation: {
          provider: "gemini", model_name: "test-only", prompt_version: "v1",
          token_usage: 0, latency_ms: 10, is_fallback: true,
          fallback_reason: "NO_TRUSTED_EVIDENCE",
        },
      };
      const frame = (event: string, data: object) =>
        `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
      await route.fulfill({
        contentType: "text/event-stream",
        body: frame("status", { request_id: "browser-test", stage: "retrieval" }) +
          frame("delta", { request_id: "browser-test", content: guidance.recommended_action }) +
          frame("complete", result),
      });
    } else {
      await route.abort();
    }
  });
  await page.goto("/dashboard/assistant");
  await expect(page.getByRole("heading", { name: "AirWise Copilot", exact: true })).toBeVisible();
  await page.getByLabel("Your environmental question").fill("Explain indoor smoke.");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.getByText("Please consent before sending a question to Gemini.")).toBeVisible();
  expect(submissions).toBe(0);
  await page.getByRole("checkbox", { name: /I agree to send/ }).check();
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.getByRole("article", { name: "Assistant guidance" })).toBeVisible();
  await expect(page.getByText("Reduce indoor smoke sources.", { exact: true })).toBeVisible();
  await expect(page.getByText("Verified live air quality is unavailable.")).toBeVisible();
  await expect(page.getByText("Indoor air quality is unmeasured.", { exact: true })).toBeVisible();
  await expect(page.getByText(/Safe guidance mode: NO_TRUSTED_EVIDENCE/)).toBeVisible();
  expect(submissions).toBe(1);
});
