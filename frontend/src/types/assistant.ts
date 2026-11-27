/**
 * TypeScript DTO contracts for AirWise Copilot conversations, SSE events, and citations.
 */

import type { z } from "zod";
import type {
  assistantEventSchema,
  chatResultSchema,
  guidanceSchema,
} from "@/lib/validation/assistant";

export type AssistantEvent = z.infer<typeof assistantEventSchema>;
export type ChatResult = z.infer<typeof chatResultSchema>;
export type AssistantGuidance = z.infer<typeof guidanceSchema>;

export interface Conversation {
  id: string;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  structured_response: AssistantGuidance | null;
  created_at: string;
}
