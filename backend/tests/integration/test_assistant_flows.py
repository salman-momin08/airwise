from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.ai.gateway.budget import TokenBudget
from app.ai.gateway.gemini import OutputModel
from app.ai.orchestration import assistant_service
from app.ai.rag.knowledge import DocumentInput, KnowledgeService
from app.core.config import Settings
from app.core.exceptions import RateLimitExceededError
from app.models.assistant import AIGenerationMetadata, ChatConversation, ChatMessage
from app.schemas.assistant import ToolPlan
from tests.ai_evaluations.test_assistant_safety import StubGateway, evidence

def headers(client: AsyncClient) -> dict[str, str]:
    return {
        "X-CSRF-Token": client.cookies.get("airwise_csrf", ""),
        "Origin": "http://localhost:3000",
    }

async def register(client: AsyncClient, email: str) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecureAssistantPass2026",
            "display_name": "Test User",
        },
    )
    assert response.status_code == 201

@pytest.fixture
def stub_gateway(monkeypatch: pytest.MonkeyPatch) -> StubGateway:
    gateway = StubGateway()

    def factory(settings: Settings, *, budget: TokenBudget) -> StubGateway:
        return gateway

    monkeypatch.setattr(assistant_service, "GeminiGateway", factory)
    return gateway

async def test_chat_auth_consent_csrf_and_cross_user_ownership(
    api_client: AsyncClient,
    stub_gateway: StubGateway,
) -> None:
    payload = {"message": "Explain indoor pollution.", "ai_consent": True}
    guest = await api_client.post("/api/v1/assistant/chat", json=payload)
    assert guest.status_code in {401, 403}
    await register(api_client, "owner@example.com")
    denied = await api_client.post("/api/v1/assistant/chat", json=payload)
    assert denied.status_code == 403
    no_consent = await api_client.post(
        "/api/v1/assistant/chat", json={**payload, "ai_consent": False}, headers=headers(api_client)
    )
    assert no_consent.status_code == 403
    assert no_consent.json()["error"]["code"] == "AI_CONSENT_REQUIRED"
    response = await api_client.post(
        "/api/v1/assistant/chat", json=payload, headers=headers(api_client)
    )
    assert response.status_code == 200
    data = response.json()["data"]
    conversation_id = data["conversation_id"]
    assert conversation_id
    assert data["generation"]["fallback_reason"] == "NO_TRUSTED_EVIDENCE"
    assert (
        len(
            (
                await api_client.get(f"/api/v1/assistant/conversations/{conversation_id}/messages")
            ).json()["data"]
        )
        == 2
    )
    api_client.cookies.clear()
    await register(api_client, "other@example.com")
    for method, path, body in (
        ("GET", f"/api/v1/assistant/conversations/{conversation_id}/messages", None),
        ("DELETE", f"/api/v1/assistant/conversations/{conversation_id}", None),
        ("POST", "/api/v1/assistant/chat", {**payload, "conversation_id": conversation_id}),
    ):
        denied = await api_client.request(method, path, json=body, headers=headers(api_client))
        assert denied.status_code == 404
    assert (await api_client.get("/api/v1/assistant/conversations")).json()["data"] == []

async def test_ingested_evidence_to_generated_response_and_saved_citation(
    api_client: AsyncClient,
    db_engine: AsyncEngine,
    stub_gateway: StubGateway,
) -> None:
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        knowledge = KnowledgeService(session, stub_gateway, "gemini-embedding-001")
        stub_gateway.document_id = await knowledge.ingest(
            DocumentInput(
                title="Indoor smoke source control",
                publisher="US EPA",
                source_url="https://www.epa.gov/indoor-air-quality-iaq/guide-air-cleaners-home",
                jurisdiction="US",
                last_reviewed_date=datetime.now(UTC),
                content=(
                    "Indoor smoke source control and suitable HEPA filtration "
                    "reduce particle exposure."
                ),
            )
        )
    await register(api_client, "grounded@example.com")
    response = await api_client.post(
        "/api/v1/assistant/chat",
        headers=headers(api_client),
        json={"message": "Explain indoor smoke control.", "ai_consent": True},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["generation"]["is_fallback"] is False
    assert data["citations"][0]["document_id"] == str(stub_gateway.document_id)
    assert data["citations"][0]["publisher"] == "US EPA"
    assert data["structured_response"]["environmental_conditions"]["status"] == "unavailable"
    async with AsyncSession(db_engine) as session:
        metadata = await session.scalar(select(AIGenerationMetadata))
        assert metadata is not None
        assert metadata.request_id == response.json()["meta"]["request_id"]
        assert "retrieve_environmental_guidelines" in metadata.tools_invoked

async def test_sse_frames_are_typed_and_persisted_history_is_exportable_and_erasable(
    api_client: AsyncClient,
    db_engine: AsyncEngine,
    stub_gateway: StubGateway,
) -> None:
    await register(api_client, "stream@example.com")
    response = await api_client.post(
        "/api/v1/assistant/chat/stream",
        json={"message": "I have chest pain and cannot breathe.", "ai_consent": True},
        headers=headers(api_client),
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    frames = []
    for frame in response.text.strip().split("\n\n"):
        event_line, data_line = frame.split("\n")
        frames.append(
            (event_line.removeprefix("event: "), json.loads(data_line.removeprefix("data: ")))
        )
    assert frames[0][0] == "status"
    assert frames[-1][0] == "complete"
    assert all("request_id" in data for _, data in frames)
    request_ids = {data["request_id"] for _, data in frames}
    assert len(request_ids) == 1
    deltas = "".join(data["content"] for event, data in frames if event == "delta")
    complete = frames[-1][1]
    assert deltas == complete["structured_response"]["recommended_action"]
    assert complete["generation"]["fallback_reason"] == "URGENT_MEDICAL_GUIDANCE"
    exported = await api_client.get("/api/v1/users/me/export")
    assert exported.status_code == 200
    assert len(exported.json()["data"]["chat_history"]) == 2
    deleted = await api_client.delete(
        "/api/v1/assistant/conversations", headers=headers(api_client)
    )
    assert deleted.status_code == 200
    async with AsyncSession(db_engine) as session:
        for model in (ChatConversation, ChatMessage, AIGenerationMetadata):
            assert await session.scalar(select(func.count()).select_from(model)) == 0

async def test_history_opt_out_does_not_store_or_reuse_conversations(
    api_client: AsyncClient,
    db_engine: AsyncEngine,
    stub_gateway: StubGateway,
) -> None:
    await register(api_client, "private@example.com")
    patch = await api_client.patch(
        "/api/v1/users/me",
        headers=headers(api_client),
        json={"preferences": {"save_chat_history": False}},
    )
    assert patch.status_code == 200
    response = await api_client.post(
        "/api/v1/assistant/chat",
        headers=headers(api_client),
        json={"message": "I have chest pain.", "ai_consent": True},
    )
    assert response.status_code == 200
    assert response.json()["data"]["conversation_id"] is None
    async with AsyncSession(db_engine) as session:
        assert await session.scalar(select(func.count()).select_from(ChatMessage)) == 0

async def test_account_erasure_removes_chat_data(
    api_client: AsyncClient,
    db_engine: AsyncEngine,
    stub_gateway: StubGateway,
) -> None:
    await register(api_client, "erase@example.com")
    response = await api_client.post(
        "/api/v1/assistant/chat",
        headers=headers(api_client),
        json={"message": "Explain indoor pollution.", "ai_consent": True},
    )
    assert response.status_code == 200
    response = await api_client.delete("/api/v1/users/me", headers=headers(api_client))
    assert response.status_code == 200
    async with AsyncSession(db_engine) as session:
        assert await session.scalar(select(func.count()).select_from(ChatConversation)) == 0
        assert await session.scalar(select(func.count()).select_from(AIGenerationMetadata)) == 0

async def test_request_rejects_unbounded_or_cross_user_tool_arguments(
    api_client: AsyncClient,
    stub_gateway: StubGateway,
) -> None:
    await register(api_client, "schema@example.com")
    response = await api_client.post(
        "/api/v1/assistant/chat",
        headers=headers(api_client),
        json={
            "message": "Explain pollution",
            "ai_consent": True,
            "user_id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 422
    response = await api_client.post(
        "/api/v1/assistant/chat",
        headers=headers(api_client),
        json={"message": "x" * 2001, "ai_consent": True},
    )
    assert response.status_code == 422
    assert not stub_gateway.prompts

async def test_sse_quota_failure_is_a_terminal_error_not_a_successful_fallback(
    api_client: AsyncClient,
    stub_gateway: StubGateway,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import AsyncMock

    await register(api_client, "quota@example.com")
    monkeypatch.setattr(
        stub_gateway,
        "generate",
        AsyncMock(side_effect=RateLimitExceededError(code="AI_DAILY_BUDGET_EXCEEDED")),
    )
    response = await api_client.post(
        "/api/v1/assistant/chat/stream",
        headers=headers(api_client),
        json={"message": "Explain indoor filtration.", "ai_consent": True},
    )
    assert "event: error" in response.text
    assert "AI_DAILY_BUDGET_EXCEEDED" in response.text
    assert "event: complete" not in response.text
    assert "event: delta" not in response.text

async def test_sse_disconnect_cancels_the_provider_and_does_not_save_partial_history(
    api_client: AsyncClient,
    db_engine: AsyncEngine,
    stub_gateway: StubGateway,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import AsyncMock

    await register(api_client, "disconnect@example.com")
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def blocked_provider(
        *,
        system: str,
        prompt: str,
        schema: type[OutputModel],
    ) -> OutputModel:
        if schema is ToolPlan:
            return schema.model_validate({"calls": []})
        started.set()
        try:
            await asyncio.Future[None]()
        finally:
            cancelled.set()
        raise AssertionError("The provider should have been cancelled.")

    monkeypatch.setattr(stub_gateway, "generate", blocked_provider)
    monkeypatch.setattr(KnowledgeService, "retrieve", AsyncMock(return_value=evidence()))
    task = asyncio.create_task(
        api_client.post(
            "/api/v1/assistant/chat/stream",
            headers=headers(api_client),
            json={"message": "Explain indoor filtration.", "ai_consent": True},
        )
    )
    await asyncio.wait_for(started.wait(), timeout=5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.wait_for(cancelled.wait(), timeout=5)
    async with AsyncSession(db_engine) as session:
        assert await session.scalar(select(func.count()).select_from(ChatMessage)) == 0
