import hashlib

from app.retrieval.hybrid import HybridRetriever
from app.schemas.conversation import Citation
from app.tools.base import ToolContext


class KnowledgeSearchTool:
    """FR-07: hybrid retrieve + rerank over approved knowledge; returns ranked
    evidence with source metadata and full citation contract fields."""

    name = "knowledge_search"

    def __init__(self, top_k: int = 3):
        self._top_k = top_k

    def run(self, ctx: ToolContext, query: str) -> dict:
        # Retriever built per call: BM25/vector legs stay fresh after
        # re-ingestion; the response cache is invalidated on ingest.
        allowed = {ctx.usecase.filters.department} if ctx.usecase.filters.department else None
        cache_key = None
        if getattr(ctx, "cache", None):
            # FR-21: cache the retrieval result — keyed by usecase +
            # department + query so responses never cross tenants.
            dept = ctx.usecase.filters.department or "all"
            qhash = hashlib.sha256(query.strip().lower().encode()).hexdigest()[:16]
            cache_key = f"kb:{ctx.usecase.usecase_id}:{dept}:{qhash}"
            hit = ctx.cache.get(cache_key)
            if hit is not None:
                return {
                    "found": hit["found"],
                    "evidence": hit["evidence"],
                    "citations": [Citation.model_validate(c) for c in hit["citations"]],
                }
        retriever = HybridRetriever(
            ctx.store.all_chunks(), ctx.store.chunk_vectors(), ctx.embedder, ctx.reranker
        )
        evidence = retriever.retrieve(query, allowed_departments=allowed, top_k=self._top_k)
        citations = [self._to_citation(i + 1, item) for i, item in enumerate(evidence)]
        if cache_key:
            ctx.cache.set(
                cache_key,
                {
                    "found": bool(evidence),
                    "evidence": evidence,
                    "citations": [c.model_dump(mode="json") for c in citations],
                },
                ttl=ctx.cache_ttl,
            )
        return {
            "found": bool(evidence),
            "evidence": evidence,
            "citations": citations,
        }

    @staticmethod
    def _to_citation(n: int, item: dict) -> Citation:
        chunk = item["chunk"]
        return Citation(
            citation_id=f"c{n}",
            document_id=chunk["document_id"],
            title=chunk["title"],
            source_system=chunk["source_system"],
            source_ref=chunk["source_url"] or chunk["source_ref"],
            page_section=chunk["section"],
            chunk_id=chunk["chunk_id"],
            excerpt=chunk["text"][:300],
            retrieval_score=item.get("retrieval_score"),
            rerank_score=item.get("rerank_score"),
            document_version=chunk["version"],
        )
