"""Ingestion pipeline (FR-10/11): source adapter -> normalize -> contextual
chunk -> embed -> upsert chunk store + vectors. Checksum-based replace
handles source drift (BRD §19); per-doc failures go to a dead-letter list.
"""

import logging
import uuid
from datetime import UTC, datetime

from app.ingestion.base import SourceAdapter
from app.ingestion.chunker import chunk_document
from app.retrieval.embeddings import Embedder
from app.stores.sqlite import SQLiteStore

logger = logging.getLogger(__name__)


class IngestionPipeline:
    def __init__(self, store: SQLiteStore, embedder: Embedder):
        self._store = store
        self._embedder = embedder

    def run(self, adapter: SourceAdapter) -> dict:
        job_id = f"job-{uuid.uuid4().hex[:8]}"
        started = datetime.now(UTC).isoformat()
        self._store.create_ingestion_job(
            {"job_id": job_id, "source": adapter.source_id, "status": "running", "started_at": started}
        )
        ingested = failed = 0
        try:
            documents = adapter.list_documents()
        except Exception as exc:
            self._store.finish_ingestion_job(
                job_id, status="failed", error=str(exc), ingested=0, failed=0
            )
            raise

        for doc in documents:
            try:
                # Source drift: unchanged checksum -> skip; changed -> replace chunks.
                existing = self._store.document_checksum(doc.doc_id)
                if existing == doc.checksum:
                    continue
                chunks = chunk_document(doc)
                vectors = {
                    c.chunk_id: self._embedder.embed(f"{c.title} {c.section} {c.text}")
                    for c in chunks
                }
                self._store.replace_document_chunks(doc.doc_id, chunks, vectors, doc.checksum)
                ingested += 1
            except Exception as exc:  # dead-letter per doc, never stop the job
                failed += 1
                self._store.add_ingestion_failure(
                    job_id, doc.doc_id, str(exc)
                )
                logger.warning(
                    "document ingestion failed",
                    extra={"action": "ingest_doc", "outcome": doc.doc_id},
                )

        self._store.finish_ingestion_job(
            job_id,
            status="completed" if failed == 0 else "completed_with_failures",
            ingested=ingested,
            failed=failed,
        )
        logger.info(
            "ingestion job finished",
            extra={"action": "ingest_job", "outcome": f"{job_id}:{ingested}/{failed}"},
        )
        return {"job_id": job_id, "source": adapter.source_id, "ingested": ingested, "failed": failed}
