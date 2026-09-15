"""Hybrid retrieval (FR-13): BM25 keyword + vector cosine merged via
reciprocal-rank fusion, ACL-filtered, then reranked with thresholding.

Local stores live in SQLite; Phase 3 swaps the legs to OpenSearch Serverless
behind this same retrieve() contract.
"""

from typing import Any

from app.retrieval.bm25 import BM25Index
from app.retrieval.corpus import Chunk
from app.retrieval.embeddings import Embedder, cosine
from app.retrieval.rerank import Reranker

RRF_K = 60  # standard reciprocal-rank-fusion constant


class HybridRetriever:
    def __init__(
        self,
        chunks: list[Chunk],
        vectors: dict[str, list[float]],
        embedder: Embedder,
        reranker: Reranker,
    ):
        self._bm25 = BM25Index(chunks)
        self._chunks = {c.chunk_id: c for c in chunks}
        self._vectors = vectors
        self._embedder = embedder
        self._reranker = reranker

    def retrieve(
        self,
        query: str,
        allowed_departments: set[str] | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Return [{chunk(dict), retrieval_score, rerank_score}] — merged,
        ACL-filtered, reranked, thresholded."""
        keyword = self._bm25.search(query, top_k=top_k * 2, allowed_departments=allowed_departments)
        vector = self._vector_search(query, allowed_departments)

        # Reciprocal rank fusion over both legs.
        fused: dict[str, float] = {}
        for rank, (chunk, _score) in enumerate(keyword):
            fused[chunk.chunk_id] = fused.get(chunk.chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)
        for rank, (chunk_id, _score) in enumerate(vector):
            fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)

        candidates = [
            {"chunk": self._chunks[cid].model_dump(mode="json"), "retrieval_score": round(score, 5)}
            for cid, score in sorted(fused.items(), key=lambda x: x[1], reverse=True)[: top_k * 2]
        ]
        return self._reranker.rerank(query, candidates, top_k=top_k)

    def _vector_search(
        self, query: str, allowed_departments: set[str] | None
    ) -> list[tuple[str, float]]:
        qv = self._embedder.embed(query)
        scored = []
        for cid, vec in self._vectors.items():
            chunk = self._chunks[cid]
            if allowed_departments is not None and "ALL" not in chunk.acl:
                if chunk.department not in allowed_departments:
                    continue
            score = cosine(qv, vec)
            if score > 0:
                scored.append((cid, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:10]
