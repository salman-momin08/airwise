from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.models.assistant import AIGenerationMetadata, ChatConversation, ChatMessage
from app.schemas.assistant import AssistantGuidance, ChatResult, ConversationData, MessageData

class AssistantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def require_conversation(
        self, *, user_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> ChatConversation:
        conversation = await self._session.scalar(
            select(ChatConversation).where(
                ChatConversation.id == conversation_id, ChatConversation.user_id == user_id
            )
        )
        if conversation is None:
            raise ResourceNotFoundError("Conversation was not found.")
        return conversation

    async def list_conversations(self, *, user_id: uuid.UUID) -> list[ConversationData]:
        records = await self._session.scalars(
            select(ChatConversation)
            .where(ChatConversation.user_id == user_id)
            .order_by(ChatConversation.created_at.desc(), ChatConversation.id.desc())
            .limit(50)
        )
        return [ConversationData(id=row.id, created_at=row.created_at) for row in records]

    async def messages(
        self, *, user_id: uuid.UUID, conversation_id: uuid.UUID, limit: int = 100
    ) -> list[MessageData]:
        await self.require_conversation(user_id=user_id, conversation_id=conversation_id)
        records = await self._session.scalars(
            select(ChatMessage)
            .join(ChatConversation)
            .where(
                ChatConversation.user_id == user_id,
                ChatMessage.conversation_id == conversation_id,
            )
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(limit)
        )
        return [
            MessageData(
                id=row.id,
                role="user" if row.role == "user" else "assistant",
                content=row.content,
                structured_response=(
                    AssistantGuidance.model_validate(row.structured_response)
                    if row.structured_response is not None
                    else None
                ),
                created_at=row.created_at,
            )
            for row in reversed(list(records))
        ]

    async def save_turn(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID | None,
        message: str,
        result: ChatResult,
    ) -> None:
        if conversation_id is None:
            conversation = ChatConversation(user_id=user_id)
            self._session.add(conversation)
            await self._session.flush()
        else:
            conversation = await self.require_conversation(
                user_id=user_id, conversation_id=conversation_id
            )
        user_message = ChatMessage(conversation_id=conversation.id, role="user", content=message)
        self._session.add(user_message)
        await self._session.flush()
        assistant_message = ChatMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=result.structured_response.recommended_action,
            structured_response=result.structured_response.model_dump(mode="json"),
        )
        self._session.add(assistant_message)
        await self._session.flush()
        info = result.generation
        self._session.add(
            AIGenerationMetadata(
                message_id=assistant_message.id,
                model_name=info.model_name,
                request_id=info.request_id,
                tools_invoked=result.tools_used,
                prompt_version=info.prompt_version,
                token_usage=info.token_usage,
                latency_ms=info.latency_ms,
                fallback_reason=info.fallback_reason,
            )
        )
        result.conversation_id = conversation.id
        result.message_id = assistant_message.id

    async def delete_history(
        self, *, user_id: uuid.UUID, conversation_id: uuid.UUID | None = None
    ) -> None:
        conversations = select(ChatConversation.id).where(ChatConversation.user_id == user_id)
        if conversation_id is not None:
            await self.require_conversation(user_id=user_id, conversation_id=conversation_id)
            conversations = conversations.where(ChatConversation.id == conversation_id)
        messages = select(ChatMessage.id).where(ChatMessage.conversation_id.in_(conversations))
        await self._session.execute(
            delete(AIGenerationMetadata).where(AIGenerationMetadata.message_id.in_(messages))
        )
        await self._session.execute(
            delete(ChatMessage).where(ChatMessage.conversation_id.in_(conversations))
        )
        await self._session.execute(
            delete(ChatConversation).where(ChatConversation.id.in_(conversations))
        )

    async def export_history(self, *, user_id: uuid.UUID) -> list[dict[str, object]]:
        # Export is intentionally unpaginated so the user receives all of their records.
        records = await self._session.execute(
            select(ChatMessage, ChatConversation.id)
            .join(ChatConversation)
            .where(ChatConversation.user_id == user_id)
            .order_by(ChatMessage.created_at, ChatMessage.id)
        )
        return [
            {
                "conversation_id": str(conversation_id),
                "id": str(message.id),
                "role": message.role,
                "content": message.content,
                "structured_response": message.structured_response,
                "created_at": message.created_at.isoformat(),
            }
            for message, conversation_id in records
        ]
