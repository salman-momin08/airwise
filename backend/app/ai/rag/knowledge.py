from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import structlog
from pgvector.sqlalchemy import Vector
from pydantic import Field, field_validator, model_validator
from sqlalchemy import String, cast, delete, func, literal_column, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gateway.gemini import LLMGateway, OutputValidationError
from app.core.exceptions import ExternalProviderUnavailableError
from app.models.assistant import (
    EMBEDDING_DIMENSIONS,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeIngestionJob,
)
from app.schemas.assistant import EvidenceReference, StrictModel

logger = structlog.get_logger(__name__)
TRUSTED_HOSTS = frozenset({"www.who.int", "www.epa.gov", "cpcb.nic.in", "ncdc.mohfw.gov.in"})

def trusted_source_url(value: str) -> str:
    parts = urlsplit(value)
    if (
        parts.scheme != "https"
        or parts.hostname not in TRUSTED_HOSTS
        or parts.username
        or parts.password
        or parts.port not in {None, 443}
        or parts.query
        or parts.fragment
    ):
        raise ValueError("Knowledge sources must be approved official HTTPS URLs.")
    return value

class DocumentInput(StrictModel):
    title: str = Field(min_length=3, max_length=300)
    publisher: str = Field(min_length=2, max_length=160)
    source_url: str = Field(max_length=1000)
    jurisdiction: str = Field(pattern=r"^(global|IN|US)$")
    publication_date: datetime | None = None
    last_reviewed_date: datetime
    content: str = Field(min_length=40, max_length=100000)

    _source = field_validator("source_url")(trusted_source_url)

    @model_validator(mode="after")
    def valid_dates(self) -> DocumentInput:
        for value in (self.publication_date, self.last_reviewed_date):
            if value is None:
                continue
            if value.tzinfo is None or value > datetime.now(UTC):
                raise ValueError("Knowledge dates must be timezone-aware and not in the future.")
        if self.publication_date is not None and self.last_reviewed_date < self.publication_date:
            raise ValueError("Review date cannot precede publication date.")
        return self

def chunk_text(text: str, *, size: int = 500, overlap: int = 80) -> list[str]:
    words = text.split()
    return [
        " ".join(words[start : start + size])
        for start in range(0, len(words), size - overlap)
        if start == 0 or start + overlap < len(words)
    ]

def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

@dataclass(frozen=True)
class RetrievedEvidence:
    reference: EvidenceReference
    content: str

class KnowledgeService:
    def __init__(self, session: AsyncSession, gateway: LLMGateway, embedding_model: str) -> None:
        self._session = session
        self._gateway = gateway
        self._embedding_model = embedding_model

    async def ingest(self, payload: DocumentInput) -> uuid.UUID:
        job = KnowledgeIngestionJob(source_url=payload.source_url, status="running")
        self._session.add(job)
        await self._session.commit()
        job_id = job.id
        try:
            if self._session.get_bind().dialect.name == "postgresql":
                # Serialize ingestion for a source even before its first row exists.
                lock_key = int(content_hash(payload.source_url)[:15], 16)
                await self._session.execute(select(func.pg_advisory_xact_lock(lock_key)))
            document = await self._session.scalar(
                select(KnowledgeDocument)
                .where(KnowledgeDocument.source_url == payload.source_url)
                .with_for_update()
            )
            chunks = chunk_text(payload.content)
            digest = content_hash(payload.content)
            if document is None:
                document = KnowledgeDocument(source_url=payload.source_url)
                self._session.add(document)
            document.title = payload.title
            document.publisher = payload.publisher
            document.jurisdiction = payload.jurisdiction
            document.publication_date = payload.publication_date
            document.last_reviewed_date = payload.last_reviewed_date
            document.trust_classification = "tier1_official"
            document.content_hash = digest
            await self._session.flush()
            existing = list(
                await self._session.scalars(
                    select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id)
                )
            )
            unchanged = (
                len(existing) == len(chunks)
                and {row.content_hash for row in existing} == {content_hash(c) for c in chunks}
                and all(row.embedding_model_version == self._embedding_model for row in existing)
            )
            if not unchanged:
                embeddings = [
                    await self._gateway.embed(chunk, task="RETRIEVAL_DOCUMENT") for chunk in chunks
                ]
                await self._session.execute(
                    delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id)
                )
                for index, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
                    self._session.add(
                        KnowledgeChunk(
                            document_id=document.id,
                            chunk_index=index,
                            content=chunk,
                            content_hash=content_hash(chunk),
                            embedding=embedding,
                            embedding_model_version=self._embedding_model,
                        )
                    )
            job.status = "succeeded"
            job.completed_at = datetime.now(UTC)
            await self._session.commit()
            return document.id
        except (ExternalProviderUnavailableError, OutputValidationError, SQLAlchemyError) as exc:
            await self._session.rollback()
            failed = await self._session.get(KnowledgeIngestionJob, job_id)
            if failed is not None:
                failed.status = "failed"
                failed.error_code = (
                    "KNOWLEDGE_STORAGE_FAILED"
                    if isinstance(exc, SQLAlchemyError)
                    else "KNOWLEDGE_EMBEDDING_FAILED"
                )
                failed.completed_at = datetime.now(UTC)
                await self._session.commit()
            logger.warning("knowledge_ingestion_failed", job_id=str(job_id))
            raise

    async def retrieve(
        self, query: str, *, jurisdiction: str, limit: int = 6
    ) -> list[RetrievedEvidence]:
        base = (
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument)
            .where(
                KnowledgeDocument.trust_classification == "tier1_official",
                KnowledgeDocument.last_reviewed_date <= datetime.now(UTC),
                KnowledgeChunk.embedding_model_version == self._embedding_model,
            )
        )
        ranks: list[list[tuple[KnowledgeChunk, KnowledgeDocument]]] = []
        if self._session.get_bind().dialect.name == "postgresql":
            vector = await self._gateway.embed(query, task="RETRIEVAL_QUERY")
            distance = cast(KnowledgeChunk.embedding, Vector(EMBEDDING_DIMENSIONS)).cosine_distance(
                vector
            )
            semantic = await self._session.execute(base.order_by(distance).limit(20))
            ranks.append([(row[0], row[1]) for row in semantic])
            language = literal_column("'english'", type_=String())
            document_vector = func.to_tsvector(language, KnowledgeChunk.content)
            search = func.plainto_tsquery(language, query)
            lexical = await self._session.execute(
                base.where(document_vector.op("@@")(search))
                .order_by(func.ts_rank_cd(document_vector, search).desc())
                .limit(20)
            )
            ranks.append([(row[0], row[1]) for row in lexical])
        else:
            # SQLite is an explicit test-only lexical path, not a production vector substitute.
            rows = await self._session.execute(base.limit(500))
            terms = set(re.findall(r"\w+", query.lower()))
            matches = [
                (len(terms & set(re.findall(r"\w+", row[0].content.lower()))), row[0], row[1])
                for row in rows
            ]
            matches.sort(key=lambda item: (-item[0], str(item[1].id)))
            ranks.append([(chunk, doc) for score, chunk, doc in matches if score])
        scores: dict[uuid.UUID, float] = {}
        candidates: dict[uuid.UUID, tuple[KnowledgeChunk, KnowledgeDocument]] = {}
        for ranking in ranks:
            for rank, (chunk, document) in enumerate(ranking):
                try:
                    trusted_source_url(document.source_url)
                except ValueError:
                    logger.warning("knowledge_source_rejected", document_id=str(document.id))
                    continue
                reviewed = document.last_reviewed_date.replace(tzinfo=UTC)
                fresh = reviewed >= datetime.now(UTC) - timedelta(days=730)
                preference = 1.15 if document.jurisdiction == jurisdiction else 1.0
                scores[chunk.id] = scores.get(chunk.id, 0) + (
                    preference * (1.0 if fresh else 0.75) / (60 + rank + 1)
                )
                candidates[chunk.id] = (chunk, document)
        result: list[RetrievedEvidence] = []
        for chunk_id in sorted(scores, key=lambda key: -scores[key])[:limit]:
            chunk, document = candidates[chunk_id]
            reviewed = document.last_reviewed_date.replace(tzinfo=UTC)
            result.append(
                RetrievedEvidence(
                    reference=EvidenceReference(
                        document_id=document.id,
                        title=document.title,
                        publisher=document.publisher,
                        source_url=document.source_url,
                        last_reviewed_date=reviewed,
                        freshness_note=(
                            "This guidance is past its review horizon; check the official source."
                            if reviewed < datetime.now(UTC) - timedelta(days=730)
                            else None
                        ),
                    ),
                    content=chunk.content,
                )
            )
        return result
