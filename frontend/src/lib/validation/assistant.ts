import { z } from "zod";

const standardSchema = z.enum(["india_naqi", "us_epa"]);

export const chatFormSchema = z.object({
  message: z.string().trim().min(1, "Enter a question.").max(2000),
  city: z.string().trim().min(2).max(100).regex(/^[\w .'-]+$/, "Enter a city name only."),
  standard: standardSchema,
  ai_consent: z.boolean().refine(Boolean, "Please consent before sending a question to Gemini."),
  use_preferences: z.boolean(),
});

export type ChatFormValues = z.infer<typeof chatFormSchema>;

const referenceSchema = z.object({
  document_id: z.string().uuid(),
  title: z.string(),
  publisher: z.string(),
  source_url: z.string().url(),
  last_reviewed_date: z.string(),
  freshness_note: z.string().nullable(),
});

const readingSchema = z.object({
  city: z.string(),
  standard: standardSchema,
  status: z.enum(["available", "unavailable"]),
  aqi: z.number().nullable(),
  category: z.string().nullable(),
  provider: z.string(),
  source_type: z.enum(["station", "model", "unavailable"]),
  measured_at: z.string().nullable(),
  is_stale: z.boolean(),
  is_development_fixture: z.boolean(),
});

export const guidanceSchema = z.object({
  situation_summary: z.string(),
  environmental_conditions: z.object({
    standard: standardSchema,
    status: z.enum(["available", "unavailable"]),
    reading: readingSchema.nullable(),
    notice: z.string(),
  }),
  recommended_action: z.string(),
  why_this_helps: z.string(),
  estimated_impact: z.object({
    metric: z.string(),
    baseline_value: z.number(),
    alternative_value: z.number(),
    estimated_difference: z.number(),
    unit: z.string(),
    methodology: z.string(),
    assumptions: z.array(z.string()),
    source_references: z.array(z.string()),
    confidence: z.enum(["low", "medium", "high"]),
    is_estimate: z.literal(true),
    calculated_at: z.string(),
  }).nullable(),
  uncertainty_or_limitations: z.string(),
  safer_alternative: z.string().nullable(),
  evidence_references: z.array(referenceSchema),
});

export const chatResultSchema = z.object({
  conversation_id: z.string().uuid().nullable(),
  message_id: z.string().uuid().nullable(),
  structured_response: guidanceSchema,
  citations: z.array(referenceSchema),
  generation: z.object({
    provider: z.string(),
    model_name: z.string(),
    prompt_version: z.string(),
    token_usage: z.number(),
    latency_ms: z.number(),
    is_fallback: z.boolean(),
    fallback_reason: z.string().nullable(),
  }),
  tools_used: z.array(z.string()),
});

const requestIdSchema = z.object({ request_id: z.string() });

export const assistantEventSchema = z.discriminatedUnion("event", [
  z.object({
    event: z.literal("status"),
    data: requestIdSchema.extend({ stage: z.string(), tool: z.string().optional() }),
  }),
  z.object({
    event: z.literal("delta"),
    data: requestIdSchema.extend({ content: z.string() }),
  }),
  z.object({
    event: z.literal("complete"),
    data: chatResultSchema.merge(requestIdSchema),
  }),
  z.object({
    event: z.literal("error"),
    data: requestIdSchema.extend({ code: z.string(), message: z.string() }),
  }),
]);
