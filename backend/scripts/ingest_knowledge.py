"""CLI utility for ingesting curated official knowledge documents and vector chunks."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import structlog
from pydantic import TypeAdapter

from app.ai.gateway.gemini import GeminiGateway
from app.ai.rag.knowledge import DocumentInput, KnowledgeService
from app.core.config import get_settings
from app.db.session import get_session_factory

logger = structlog.get_logger(__name__)


async def ingest_manifest(path: Path) -> list[str]:
    """Validate and ingest local operator-approved knowledge documents."""
    # Operator-supplied local manifests only: ingestion never fetches arbitrary URLs.
    documents = TypeAdapter(list[DocumentInput]).validate_json(
        await asyncio.to_thread(path.read_bytes)
    )
    settings = get_settings()
    gateway = GeminiGateway(settings)
    async with get_session_factory()() as session:
        service = KnowledgeService(session, gateway, settings.embedding_model)
        return [str(await service.ingest(document)) for document in documents]


def main() -> None:
    """Parse CLI arguments and run knowledge-base manifest ingestion."""
    parser = argparse.ArgumentParser(
        description="Ingest reviewed official-source knowledge summaries."
    )
    parser.add_argument(
        "manifest",
        type=Path,
        nargs="?",
        default=Path(__file__).with_name("knowledge_sources.json"),
    )
    args = parser.parse_args()
    identifiers = asyncio.run(ingest_manifest(args.manifest))
    logger.info("knowledge_manifest_ingested", document_count=len(identifiers))


if __name__ == "__main__":
    main()
