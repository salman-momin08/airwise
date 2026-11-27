from __future__ import annotations

import asyncio
import math
import time
from typing import Literal, Protocol, TypeVar

import httpx
import structlog
from pydantic import BaseModel, Field, ValidationError

from app.ai.gateway.budget import TokenBudget
from app.core.config import Settings
from app.core.exceptions import ExternalProviderUnavailableError
from app.core.telemetry import telemetry_registry
from app.models.assistant import EMBEDDING_DIMENSIONS

logger = structlog.get_logger(__name__)
OutputModel = TypeVar("OutputModel", bound=BaseModel)

class OutputValidationError(ValueError):
    """The provider returned content outside the requested output contract."""

class LLMGateway(Protocol):
    model_name: str
    token_usage: int

    async def generate(
        self, *, system: str, prompt: str, schema: type[OutputModel]
    ) -> OutputModel: ...

    async def embed(
        self, text: str, *, task: Literal["RETRIEVAL_QUERY", "RETRIEVAL_DOCUMENT"]
    ) -> list[float]: ...

class GeminiPart(BaseModel):
    text: str = ""
    thought: bool = False

class GeminiContent(BaseModel):
    parts: list[GeminiPart] = Field(default_factory=list)

class GeminiCandidate(BaseModel):
    content: GeminiContent = Field(default_factory=GeminiContent)
    finish_reason: str = Field(default="", alias="finishReason")

class GeminiUsage(BaseModel):
    total_token_count: int = Field(default=0, ge=0, alias="totalTokenCount")

class GeminiResponse(BaseModel):
    candidates: list[GeminiCandidate] = Field(default_factory=list, max_length=1)
    usage_metadata: GeminiUsage = Field(default_factory=GeminiUsage, alias="usageMetadata")

class GeminiEmbedding(BaseModel):
    values: list[float] = Field(min_length=EMBEDDING_DIMENSIONS, max_length=EMBEDDING_DIMENSIONS)

class GeminiEmbeddingResponse(BaseModel):
    embedding: GeminiEmbedding

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/"
_GEMINI_TIMEOUT = httpx.Timeout(20.0, connect=3.0)
_GEMINI_LIMITS = httpx.Limits(max_keepalive_connections=10, max_connections=30)
_shared_gemini_client: httpx.AsyncClient | None = None
_shared_gemini_loop: asyncio.AbstractEventLoop | None = None

def _get_shared_gemini_client() -> httpx.AsyncClient:
    global _shared_gemini_client, _shared_gemini_loop
    current_loop = asyncio.get_running_loop()
    if (
        _shared_gemini_client is None
        or _shared_gemini_client.is_closed
        or _shared_gemini_loop is not current_loop
    ):
        _shared_gemini_client = httpx.AsyncClient(
            base_url=_GEMINI_BASE_URL,
            timeout=_GEMINI_TIMEOUT,
            limits=_GEMINI_LIMITS,
            follow_redirects=False,
        )
        _shared_gemini_loop = current_loop
    return _shared_gemini_client

async def close_gemini_http_client() -> None:
    """Close pooled Gemini HTTP client on application shutdown."""
    global _shared_gemini_client, _shared_gemini_loop
    client = _shared_gemini_client
    _shared_gemini_client = None
    _shared_gemini_loop = None
    if client is not None and not client.is_closed:
        await client.aclose()

class GeminiGateway:
    """Backend-only Gemini REST adapter with pooled connections, retries, and circuit breaker."""

    _failures = 0
    _open_until = 0.0

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        budget: TokenBudget | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._budget = budget
        self.model_name = settings.gemini_model
        self.token_usage = 0

    async def _post_with_client(
        self,
        client: httpx.AsyncClient,
        model: str,
        method: str,
        body: dict[str, object],
    ) -> httpx.Response:
        req_headers = {"x-goog-api-key": self._settings.gemini_api_key}
        for attempt in range(2):
            if self._budget is not None:
                # UTF-8 bytes conservatively bound input tokens; charge retries too.
                await self._budget.reserve(
                    len(str(body).encode("utf-8")) + self._settings.ai_max_output_tokens
                )
            try:
                if method == "generateContent":
                    telemetry_registry.llm_requests_total += 1
                response = await client.post(
                    f"models/{model}:{method}",
                    headers=req_headers,
                    json=body,
                )
                if attempt == 0 and (response.status_code == 429 or response.status_code >= 500):
                    retry_after = response.headers.get("Retry-After", "")
                    delay = float(retry_after) if retry_after.isdecimal() else 0.5
                    await asyncio.sleep(min(delay, 1.5))
                    continue
                response.raise_for_status()
                type(self)._failures = 0
                return response
            except (httpx.HTTPError, httpx.InvalidURL) as exc:
                # Exception strings can include request details: log only the class.
                logger.warning("gemini_request_failed", error_type=type(exc).__name__)
                if attempt == 0 and isinstance(exc, httpx.TransportError):
                    await asyncio.sleep(0.5)
                    continue
                type(self)._failures += 1
                if type(self)._failures >= 3:
                    type(self)._open_until = time.monotonic() + 30
                raise ExternalProviderUnavailableError(
                    code="AI_PROVIDER_UNAVAILABLE",
                    message="Gemini is temporarily unavailable.",
                ) from None
        raise RuntimeError("Gemini request loop ended unexpectedly.")

    async def _post(self, model: str, method: str, body: dict[str, object]) -> httpx.Response:
        if not self._settings.gemini_api_key:
            raise ExternalProviderUnavailableError(
                code="AI_NOT_CONFIGURED", message="The Gemini API key has not been configured."
            )
        if time.monotonic() < type(self)._open_until:
            raise ExternalProviderUnavailableError(
                code="AI_CIRCUIT_OPEN",
                message="Gemini is temporarily unavailable; try again shortly.",
            )
        if self._transport is not None:
            async with httpx.AsyncClient(
                base_url=_GEMINI_BASE_URL,
                timeout=_GEMINI_TIMEOUT,
                follow_redirects=False,
                transport=self._transport,
            ) as isolated_client:
                return await self._post_with_client(isolated_client, model, method, body)

        return await self._post_with_client(
            _get_shared_gemini_client(), model, method, body
        )

    async def generate(self, *, system: str, prompt: str, schema: type[OutputModel]) -> OutputModel:
        if len(prompt) > 24000 or len(system) > 12000:
            raise ValueError("AI context exceeds the configured request bounds.")
        response = await self._post(
            self.model_name,
            "generateContent",
            {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseJsonSchema": schema.model_json_schema(),
                    "maxOutputTokens": self._settings.ai_max_output_tokens,
                    "temperature": 0.1,
                    "thinkingConfig": {"thinkingBudget": 0},
                },
            },
        )
        try:
            payload = GeminiResponse.model_validate_json(response.content)
            self.token_usage += payload.usage_metadata.total_token_count
            if not payload.candidates or payload.candidates[0].finish_reason != "STOP":
                raise OutputValidationError("Gemini did not produce a complete response.")
            text = "".join(
                part.text for part in payload.candidates[0].content.parts if not part.thought
            )
            return schema.model_validate_json(text)
        except ValidationError:
            raise OutputValidationError("Gemini output failed schema validation.") from None

    async def embed(
        self, text: str, *, task: Literal["RETRIEVAL_QUERY", "RETRIEVAL_DOCUMENT"]
    ) -> list[float]:
        response = await self._post(
            self._settings.embedding_model,
            "embedContent",
            {
                "model": f"models/{self._settings.embedding_model}",
                "content": {"parts": [{"text": text}]},
                "taskType": task,
                "outputDimensionality": EMBEDDING_DIMENSIONS,
            },
        )
        try:
            values = GeminiEmbeddingResponse.model_validate_json(response.content).embedding.values
            norm = math.sqrt(sum(value * value for value in values))
            if not math.isfinite(norm) or norm == 0:
                raise OutputValidationError("Gemini returned an invalid embedding.")
            return [value / norm for value in values]
        except ValidationError:
            raise OutputValidationError("Gemini embedding failed schema validation.") from None
