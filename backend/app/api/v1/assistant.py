"""Authenticated `/api/v1/assistant` chat, SSE streaming, and conversation history endpoints."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.orchestration.assistant_service import AssistantService
from app.ai.prompts.system_prompts import PROMPT_VERSION
from app.ai.tools.registry import ALLOWLISTED_AI_TOOLS, MAX_TOOL_CALL_DEPTH
from app.api.dependencies import (
    AuthenticatedPrincipal,
    enforce_csrf_protection,
    get_app_settings,
    get_response_meta,
    require_authenticated_user,
)
from app.core.config import Settings
from app.core.exceptions import AirWiseError
from app.db.session import get_db_session
from app.repositories.assistant_repository import AssistantRepository
from app.schemas.assistant import ChatRequest, ChatResult, ConversationData, MessageData
from app.schemas.common import ApiResponse, ResponseMeta

router = APIRouter(prefix="/assistant", tags=["assistant"])
logger = structlog.get_logger(__name__)
Principal = Annotated[AuthenticatedPrincipal, Depends(require_authenticated_user)]
Database = Annotated[AsyncSession, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_app_settings)]
Meta = Annotated[ResponseMeta, Depends(get_response_meta)]


@router.get("/capabilities", response_model=ApiResponse[dict[str, object]])
async def get_assistant_capabilities(
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[dict[str, object]]:
    return ApiResponse(
        data={
            "assistant_name": "AirWise Copilot",
            "prompt_version": PROMPT_VERSION,
            "max_tool_call_depth": MAX_TOOL_CALL_DEPTH,
            "allowlisted_tools": [
                {"name": t.name, "auth_scope": t.auth_scope.value, "description": t.description}
                for t in ALLOWLISTED_AI_TOOLS
            ],
        },
        meta=meta,
    )


@router.post(
    "/chat",
    response_model=ApiResponse[ChatResult],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def chat(
    payload: ChatRequest, principal: Principal, db: Database, settings: AppSettings, meta: Meta
) -> ApiResponse[ChatResult]:
    service = AssistantService(db, settings, principal.user_id, request_id=meta.request_id)
    save_history = await service.authorize(payload)
    data = await service.run(payload, save_history=save_history)
    return ApiResponse(data=data, meta=meta)


async def _produce_assistant_events(
    *,
    service: AssistantService,
    payload: ChatRequest,
    save_history: bool,
    queue: asyncio.Queue[tuple[str, dict[str, object]] | None],
) -> None:
    async def emit(stage: str, tool: str | None) -> None:
        data: dict[str, object] = {"stage": stage}
        if tool is not None:
            data["tool"] = tool
        await queue.put(("status", data))

    try:
        result = await service.run(payload, save_history=save_history, emit=emit)
        # Only validated content is released. Raw provider tokens may contain
        # hallucinations or unsafe advice and must never reach the client.
        content = result.structured_response.recommended_action
        for start in range(0, len(content), 80):
            await queue.put(("delta", {"content": content[start : start + 80]}))
        await queue.put(("complete", result.model_dump(mode="json")))
    except AirWiseError as exc:
        await queue.put(("error", {"code": exc.code, "message": exc.message}))
    except SQLAlchemyError as exc:
        logger.error("assistant_persistence_failed", error_type=type(exc).__name__)
        await queue.put(
            (
                "error",
                {
                    "code": "AI_PERSISTENCE_UNAVAILABLE",
                    "message": "The response could not be saved. Please try again.",
                },
            )
        )
    finally:
        await queue.put(None)


async def _stream_assistant_events(
    *,
    service: AssistantService,
    payload: ChatRequest,
    save_history: bool,
    request: Request,
    request_id: str,
) -> AsyncIterator[str]:
    queue: asyncio.Queue[tuple[str, dict[str, object]] | None] = asyncio.Queue()
    task = asyncio.create_task(
        _produce_assistant_events(
            service=service, payload=payload, save_history=save_history, queue=queue
        )
    )
    try:
        while (event := await queue.get()) is not None:
            if await request.is_disconnected():
                break
            name, data = event
            data["request_id"] = request_id
            yield f"event: {name}\ndata: {json.dumps(data)}\n\n"
        if task.done():
            await task
    finally:
        if not task.done():
            task.cancel()
        with suppress(asyncio.CancelledError):
            await task


@router.post("/chat/stream", dependencies=[Depends(enforce_csrf_protection)])
async def stream_chat(
    payload: ChatRequest,
    request: Request,
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> StreamingResponse:
    service = AssistantService(db, settings, principal.user_id, request_id=meta.request_id)
    save_history = await service.authorize(payload)
    return StreamingResponse(
        _stream_assistant_events(
            service=service,
            payload=payload,
            save_history=save_history,
            request=request,
            request_id=meta.request_id,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations", response_model=ApiResponse[list[ConversationData]])
async def list_conversations(
    principal: Principal,
    db: Database,
    meta: Meta,
) -> ApiResponse[list[ConversationData]]:
    data = await AssistantRepository(db).list_conversations(user_id=principal.user_id)
    return ApiResponse(data=data, meta=meta)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=ApiResponse[list[MessageData]],
)
async def list_messages(
    conversation_id: uuid.UUID,
    principal: Principal,
    db: Database,
    meta: Meta,
) -> ApiResponse[list[MessageData]]:
    data = await AssistantRepository(db).messages(
        user_id=principal.user_id, conversation_id=conversation_id
    )
    return ApiResponse(data=data, meta=meta)


@router.delete(
    "/conversations",
    response_model=ApiResponse[dict[str, str]],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def delete_history(
    principal: Principal,
    db: Database,
    meta: Meta,
) -> ApiResponse[dict[str, str]]:
    await AssistantRepository(db).delete_history(user_id=principal.user_id)
    await db.commit()
    return ApiResponse(data={"status": "deleted"}, meta=meta)


@router.delete(
    "/conversations/{conversation_id}",
    response_model=ApiResponse[dict[str, str]],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def delete_conversation(
    conversation_id: uuid.UUID,
    principal: Principal,
    db: Database,
    meta: Meta,
) -> ApiResponse[dict[str, str]]:
    await AssistantRepository(db).delete_history(
        user_id=principal.user_id, conversation_id=conversation_id
    )
    await db.commit()
    return ApiResponse(data={"status": "deleted"}, meta=meta)
