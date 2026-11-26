import { describe, expect, it, vi } from "vitest";
import { consumeAssistantStream, assistantApi } from "@/lib/api/assistant";
import { chatFormSchema } from "@/lib/validation/assistant";

const guidance = {
  situation_summary: "General protection guidance.",
  environmental_conditions: {
    standard: "india_naqi", status: "unavailable", reading: null,
    notice: "Live air quality is unavailable.",
  },
  recommended_action: "Reduce indoor smoke sources.",
  why_this_helps: "Source control can reduce exposure.",
  estimated_impact: null,
  uncertainty_or_limitations: "Indoor air quality is unmeasured.",
  safer_alternative: null,
  evidence_references: [],
};
const result = {
  conversation_id: null, message_id: null, structured_response: guidance, citations: [],
  generation: {
    provider: "gemini", model_name: "gemini-test", prompt_version: "v1",
    token_usage: 0, latency_ms: 10, is_fallback: true, fallback_reason: "NO_TRUSTED_EVIDENCE",
  },
  tools_used: [],
  request_id: "request-test",
};

function frame(event: string, data: object): string {
  return `event: ${event}\r\ndata: ${JSON.stringify(data)}\r\n\r\n`;
}

function response(chunks: Uint8Array[]): Response {
  return new Response(new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(chunk);
      controller.close();
    },
  }), { headers: { "Content-Type": "text/event-stream" } });
}

describe("Assistant event stream", () => {
  it("parses split UTF-8 bytes and CRLF frames and requires validated completion", async () => {
    const encoder = new TextEncoder();
    const bytes = encoder.encode(
      frame("status", { request_id: "request-test", stage: "retrieval" }) +
      frame("delta", { request_id: "request-test", content: "Clean air \u2014 protect exposure" }) +
      frame("complete", result),
    );
    const events: string[] = [];
    const chunks = Array.from(bytes, (byte) => new Uint8Array([byte]));
    const output = await consumeAssistantStream(response(chunks), (event) => events.push(event.event));
    expect(events).toEqual(["status", "delta", "complete"]);
    expect(output.structured_response.recommended_action).toBe(guidance.recommended_action);
  });

  it("reports truncated streams and typed API errors rather than successful partial text", async () => {
    const encoder = new TextEncoder();
    await expect(consumeAssistantStream(response([
      encoder.encode(frame("delta", { request_id: "test", content: "Partial" })),
    ]), () => {})).rejects.toThrow("before a complete response");
    await expect(consumeAssistantStream(response([
      encoder.encode(frame("error", { request_id: "test", code: "AI_LIMIT", message: "Limit reached" })),
    ]), () => {})).rejects.toThrow("Limit reached");
  });

  it("cancels a pending read when the user stops the response", async () => {
    const controller = new AbortController();
    const cancel = vi.fn();
    const pending = new Response(new ReadableStream({ cancel }), {
      headers: { "Content-Type": "text/event-stream" },
    });
    const promise = consumeAssistantStream(pending, () => {}, controller.signal);
    controller.abort(new DOMException("Stopped", "AbortError"));
    await expect(promise).rejects.toThrow("Stopped");
    expect(cancel).toHaveBeenCalled();
  });

  it("forbids incomplete or invalid structured completion payloads", async () => {
    const encoder = new TextEncoder();
    await expect(consumeAssistantStream(response([
      encoder.encode(frame("complete", { request_id: "test" })),
    ]), () => {})).rejects.toThrow();
  });

  it("requires explicit consent and sends the existing CSRF cookie on streaming POST", async () => {
    const values = {
      message: "Explain indoor air.", city: "Delhi", standard: "india_naqi" as const,
      ai_consent: false, use_preferences: false,
    };
    expect(chatFormSchema.safeParse(values).success).toBe(false);
    document.cookie = "airwise_csrf=csrf-test; Path=/";
    const fetch = vi.fn().mockResolvedValue(response([
      new TextEncoder().encode(frame("complete", result)),
    ]));
    vi.stubGlobal("fetch", fetch);
    try {
      await assistantApi.stream(
        { ...values, ai_consent: true }, null, () => {}, new AbortController().signal,
      );
      const options = fetch.mock.calls[0][1] as RequestInit;
      expect(new Headers(options.headers).get("X-CSRF-Token")).toBe("csrf-test");
      expect(options.credentials).toBe("include");
      expect(JSON.parse(String(options.body)).ai_consent).toBe(true);
    } finally {
      vi.unstubAllGlobals();
      document.cookie = "airwise_csrf=; Max-Age=0; Path=/";
    }
  });
});
