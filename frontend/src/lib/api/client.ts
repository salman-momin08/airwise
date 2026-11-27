import type { ApiErrorEnvelope, ApiResponse } from "@/types/api";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  (process.env.NODE_ENV === "production" ? "/api/v1" : "http://localhost:8000/api/v1");

function readCsrfCookie(): string | undefined {
  if (typeof document === "undefined") return undefined;
  const match = document.cookie
    .split("; ")
    .find((entry) => entry.startsWith("airwise_csrf="));
  return match ? decodeURIComponent(match.split("=")[1] ?? "") : undefined;
}

export class ApiClientError extends Error {
  readonly code: string;
  readonly requestId: string;
  readonly status: number;

  constructor(code: string, message: string, requestId: string, status: number) {
    super(message);
    this.name = "ApiClientError";
    this.code = code;
    this.requestId = requestId;
    this.status = status;
  }
}

const MUTATION_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function buildRequestHeaders(method: string, options: RequestInit): Headers {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (MUTATION_METHODS.has(method)) {
    const csrf = readCsrfCookie();
    if (csrf) {
      headers.set("X-CSRF-Token", csrf);
    }
  }
  return headers;
}

async function parseApiClientError(response: Response): Promise<ApiClientError> {
  let errorBody: ApiErrorEnvelope | null = null;
  try {
    errorBody = (await response.json()) as ApiErrorEnvelope;
  } catch {
    // Non-JSON upstream failure
  }
  const detail = errorBody?.error;
  return new ApiClientError(
    detail?.code ?? "HTTP_REQUEST_FAILED",
    detail?.message ?? `Request failed with status ${response.status}`,
    detail?.request_id ?? "unknown",
    response.status,
  );
}

export async function apiFetch(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  const method = (options.method ?? "GET").toUpperCase();
  const headers = buildRequestHeaders(method, options);

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    method,
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    throw await parseApiClientError(response);
  }

  return response;
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<ApiResponse<T>> {
  const response = await apiFetch(path, options);
  return (await response.json()) as ApiResponse<T>;
}
