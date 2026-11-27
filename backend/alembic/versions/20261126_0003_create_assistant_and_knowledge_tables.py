"""Create trusted knowledge, chat history and AI generation metadata.

Revision ID: 20261126_0003
Revises: 20261125_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "20261126_0003"
down_revision: str | None = "20261125_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    is_pg = op.get_bind().dialect.name == "postgresql"
    if is_pg:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    json_type = postgresql.JSONB() if is_pg else sa.JSON()
    vector_type = Vector(768) if is_pg else sa.JSON()
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("publisher", sa.String(160), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False, unique=True),
        sa.Column("jurisdiction", sa.String(32), nullable=False),
        sa.Column("trust_classification", sa.String(32), nullable=False),
        sa.Column("publication_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reviewed_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id", sa.Uuid(), sa.ForeignKey("knowledge_documents.id"), nullable=False
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedding", vector_type, nullable=False),
        sa.Column("embedding_model_version", sa.String(100), nullable=False),
        sa.UniqueConstraint("document_id", "chunk_index"),
    )
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    if is_pg:
        op.execute(
            "CREATE INDEX ix_knowledge_chunks_embedding ON knowledge_chunks "
            "USING hnsw (embedding vector_cosine_ops)"
        )
        op.execute(
            "CREATE INDEX ix_knowledge_chunks_lexical ON knowledge_chunks "
            "USING gin (to_tsvector('english', content))"
        )
    op.create_table(
        "knowledge_ingestion_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "chat_conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_chat_conversations_user_id", "chat_conversations", ["user_id"])
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id", sa.Uuid(), sa.ForeignKey("chat_conversations.id"), nullable=False
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("structured_response", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_chat_messages_conversation_id", "chat_messages", ["conversation_id"])
    op.create_table(
        "ai_generation_metadata",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "message_id", sa.Uuid(), sa.ForeignKey("chat_messages.id"), nullable=False, unique=True
        ),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("tools_invoked", json_type, nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(100), nullable=False),
        sa.Column("token_usage", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("fallback_reason", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

def downgrade() -> None:
    for table in (
        "ai_generation_metadata",
        "chat_messages",
        "chat_conversations",
        "knowledge_ingestion_jobs",
        "knowledge_chunks",
        "knowledge_documents",
    ):
        op.drop_table(table)
