import { apiFetch, apiRequest, ApiClientError } from "@/lib/api/client";
import { assistantEventSchema, type ChatFormValues } from "@/lib/validation/assistant";
import type { AssistantEvent, ChatMessage, ChatResult, Conversation } from "@/types/assistant";

export async function consumeAssistantStream(
  response: Response,
  onEvent: (event: AssistantEvent) => void,
  signal?: AbortSignal,
): Promise<ChatResult> {
  if (!response.headers.get("Content-Type")?.includes("text/event-stream") || !response.body) {
    throw new Error("The assistant did not return an event stream.");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const abort = () => { void reader.cancel(signal?.reason); };
  signal?.addEventListener("abort", abort, { once: true });
  try {
    while (true) {
      signal?.throwIfAborted();
      const { value, done } = await reader.read();
      signal?.throwIfAborted();
      buffer += decoder.decode(value, { stream: !done });
      buffer = buffer.replace(/\r\n/g, "\n");
      if (buffer.length > 1_000_000) throw new Error("The assistant response exceeded its limit.");
      let end: number;
      while ((end = buffer.indexOf("\n\n")) >= 0) {
        const frame = buffer.slice(0, end);
        buffer = buffer.slice(end + 2);
        const lines = frame.split("\n");
        const name = lines.find((line) => line.startsWith("event:"))?.slice(6).trim();
        const data = lines.filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trimStart()).join("\n");
        if (!data && (!name || frame.startsWith(":"))) continue;
        const payload: unknown = JSON.parse(data);
        const event = assistantEventSchema.parse({ event: name, data: payload });
        if (event.event === "error") {
          throw new ApiClientError(event.data.code, event.data.message, event.data.request_id, 503);
        }
        onEvent(event);
        if (event.event === "complete") return event.data;
      }
      if (done) throw new Error("The assistant stream ended before a complete response. Please retry.");
    }
  } finally {
    signal?.removeEventListener("abort", abort);
    await reader.cancel();
    reader.releaseLock();
  }
}

export const assistantApi = {
  listConversations: () => apiRequest<Conversation[]>("/assistant/conversations"),
  messages: (id: string) => apiRequest<ChatMessage[]>(`/assistant/conversations/${id}/messages`),
  deleteHistory: () => apiRequest<{ status: string }>("/assistant/conversations", { method: "DELETE" }),
  stream: async (
    values: ChatFormValues,
    conversationId: string | null,
    onEvent: (event: AssistantEvent) => void,
    signal: AbortSignal,
  ) => {
    const response = await apiFetch("/assistant/chat/stream", {
      method: "POST",
      body: JSON.stringify({ ...values, conversation_id: conversationId }),
      signal,
    });
    return consumeAssistantStream(response, onEvent, signal);
  },
};
