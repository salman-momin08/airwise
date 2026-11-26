from __future__ import annotations

import json
import uuid

import httpx
import pytest

from app.ai.gateway.budget import TokenBudget
from app.ai.gateway.gemini import GeminiGateway, OutputValidationError
from app.core.config import Settings
from app.core.exceptions import ExternalProviderUnavailableError, RateLimitExceededError
from app.schemas.assistant import ToolPlan


async def test_gemini_structured_output_and_embedding_rest_contract() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith(":embedContent"):
            return httpx.Response(200, json={"embedding": {"values": [2.0] + [0.0] * 767}})
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"parts": [{"text": '{"calls": []}'}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {"totalTokenCount": 17},
            },
        )

    settings = Settings(app_env="test", gemini_api_key="not-a-real-api-key")
    gateway = GeminiGateway(settings, transport=httpx.MockTransport(respond))
    result = await gateway.generate(system="Select tools.", prompt="Indoor air", schema=ToolPlan)
    assert result.calls == []
    assert gateway.token_usage == 17
    vector = await gateway.embed("Indoor smoke", task="RETRIEVAL_QUERY")
    assert vector[0] == 1.0 and len(vector) == 768
    assert all(request.url.host == "generativelanguage.googleapis.com" for request in requests)
    assert all("key=" not in str(request.url) for request in requests)
    assert requests[0].headers["x-goog-api-key"] == settings.gemini_api_key
    body = json.loads(requests[0].content)
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["generationConfig"]["responseJsonSchema"]["title"] == "ToolPlan"
    assert json.loads(requests[1].content)["outputDimensionality"] == 768


@pytest.mark.parametrize(
    "response",
    [
        {"candidates": []},
        {"candidates": [{"finishReason": "MAX_TOKENS"}]},
        {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "not JSON"}]}}]},
    ],
)
async def test_blocked_truncated_and_malformed_outputs_are_rejected(
    response: dict[str, object],
) -> None:
    gateway = GeminiGateway(
        Settings(app_env="test", gemini_api_key="test-key"),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=response)),
    )
    with pytest.raises(OutputValidationError):
        await gateway.generate(system="Tools", prompt="Question", schema=ToolPlan)


async def test_missing_key_and_redirect_are_not_followed() -> None:
    gateway = GeminiGateway(Settings(app_env="test", gemini_api_key=""))
    with pytest.raises(ExternalProviderUnavailableError, match="not been configured"):
        await gateway.generate(system="Tools", prompt="Question", schema=ToolPlan)
    requests: list[httpx.Request] = []

    def redirect(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(302, headers={"Location": "http://127.0.0.1/private"})

    gateway = GeminiGateway(
        Settings(app_env="test", gemini_api_key="test-key"),
        transport=httpx.MockTransport(redirect),
    )
    with pytest.raises(ExternalProviderUnavailableError):
        await gateway.generate(system="Tools", prompt="Question", schema=ToolPlan)
    assert len(requests) == 1


async def test_per_user_daily_budget_is_bounded_and_isolated() -> None:
    settings = Settings(app_env="test", ai_daily_token_budget=1000)
    first = TokenBudget(settings, uuid.uuid4())
    second = TokenBudget(settings, uuid.uuid4())
    await first.reserve(800)
    with pytest.raises(RateLimitExceededError):
        await first.reserve(201)
    await second.reserve(1000)
