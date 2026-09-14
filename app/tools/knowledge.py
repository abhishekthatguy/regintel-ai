from app.retrieval.corpus import Chunk
from app.schemas.conversation import Citation
from app.tools.base import ToolContext

# Below this normalized score the evidence is too weak to ground an answer.
MIN_SCORE = 1.0


class KnowledgeSearchTool:
    """FR-07: search approved knowledge, return ranked evidence + metadata."""

    name = "knowledge_search"

    def __init__(self, top_k: int = 3):
        self._top_k = top_k

    def run(self, ctx: ToolContext, query: str) -> dict:
        allowed = {ctx.usecase.filters.department} if ctx.usecase.filters.department else None
        results = ctx.index.search(query, top_k=self._top_k, allowed_departments=allowed)
        evidence = [
            {"chunk": chunk, "score": score}
            for chunk, score in results
            if score >= MIN_SCORE
        ]
        return {
            "found": bool(evidence),
            "evidence": evidence,
            "citations": [
                self._to_citation(i + 1, item["chunk"], item["score"])
                for i, item in enumerate(evidence)
            ],
        }

    @staticmethod
    def _to_citation(n: int, chunk: Chunk, score: float) -> Citation:
        return Citation(
            citation_id=f"c{n}",
            document_id=chunk.document_id,
            title=chunk.title,
            source_system=chunk.source_system,
            source_ref=chunk.source_ref,
            page_section=chunk.section,
            chunk_id=chunk.chunk_id,
            excerpt=chunk.text[:300],
            retrieval_score=round(score, 3),
            document_version=chunk.version,
        )
