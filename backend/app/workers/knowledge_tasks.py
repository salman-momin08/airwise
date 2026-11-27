"""Idempotent Celery task ingesting curated official knowledge documents."""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.workers.celery_app import celery_app
from scripts.ingest_knowledge import ingest_manifest


@celery_app.task(name="app.workers.knowledge_tasks.ingest_curated_knowledge")
def ingest_curated_knowledge() -> dict[str, object]:
    manifest = Path(__file__).resolve().parents[2] / "scripts" / "knowledge_sources.json"
    identifiers = asyncio.run(ingest_manifest(manifest))
    return {"status": "completed", "document_ids": identifiers}
