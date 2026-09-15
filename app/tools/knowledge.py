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
        # re-ingestion without any cache invalidation (small local corpus).
        retriever = HybridRetriever(
            ctx.store.all_chunks(), ctx.store.chunk_vectors(), ctx.embedder, ctx.reranker
        )
        allowed = {ctx.usecase.filters.department} if ctx.usecase.filters.department else None
        evidence = retriever.retrieve(query, allowed_departments=allowed, top_k=self._top_k)
        return {
            "found": bool(evidence),
            "evidence": evidence,
            "citations": [self._to_citation(i + 1, item) for i, item in enumerate(evidence)],
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
