"""Reranker implementations (FR-14).

- LocalReranker: exact-phrase and coverage rescoring, no external calls.
- CohereRerank: Bedrock Cohere Rerank when configured (Phase 3).
"""

from typing import Any, Protocol

from app.retrieval.bm25 import tokenize

# Candidates below this rerank score are dropped as weak evidence (FR-14).
DEFAULT_RERANK_THRESHOLD = 0.05


class Reranker(Protocol):
    model_id: str

    def rerank(
        self, query: str, candidates: list[dict[str, Any]], top_k: int = 5
    ) -> list[dict[str, Any]]:
        """Each candidate carries chunk + retrieval_score; returns them with
        rerank_score set, reordered, thresholded."""


class LocalReranker:
    """Boosts exact-phrase matches, title/section hits and query coverage."""

    model_id = "local-reranker-v1"

    def __init__(self, threshold: float = DEFAULT_RERANK_THRESHOLD):
        self.threshold = threshold

    def rerank(self, query: str, candidates: list[dict[str, Any]], top_k: int = 5) -> list[dict[str, Any]]:
        terms = set(tokenize(query))
        scored = []
        for cand in candidates:
            chunk = cand["chunk"]
            title_text = f"{chunk['title']} {chunk['section']}"
            body = chunk["text"]

            overlap = len(terms & set(tokenize(body))) / max(len(terms), 1)
            phrase = 1.0 if query.lower().strip() in body.lower() else 0.0
            title_hit = len(terms & set(tokenize(title_text))) / max(len(terms), 1)

            rerank = (0.45 * overlap) + (0.35 * phrase) + (0.20 * title_hit)
            cand["rerank_score"] = round(rerank, 3)
            scored.append(cand)

        scored = [c for c in scored if c["rerank_score"] >= self.threshold]
        scored.sort(key=lambda c: c["rerank_score"], reverse=True)
        return scored[:top_k]


class CohereRerank:
    """Cohere Rerank via Bedrock; falls back to LocalReranker when the
    client isn't configured (keeps local demo working)."""

    def __init__(self, model_id: str = "cohere.rerank-v3-5:0"):
        self.model_id = model_id
        self._fallback = LocalReranker()
        try:
            import os

            import boto3

            self._client = boto3.client(
                "bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1")
            )
        except Exception:
            self._client = None

    def rerank(self, query: str, candidates: list[dict[str, Any]], top_k: int = 5) -> list[dict[str, Any]]:
        if not self._client:
            return self._fallback.rerank(query, candidates, top_k)
        import json

        resp = self._client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(
                {
                    "query": query,
                    "documents": [c["chunk"]["text"] for c in candidates],
                    "top_n": top_k,
                    "api_version": 2,
                }
            ),
        )
        results = json.loads(resp["body"].read()).get("results", [])
        out = []
        for r in results:
            cand = candidates[r["index"]]
            cand["rerank_score"] = r["relevance_score"]
            out.append(cand)
        return out


def get_reranker(configured: str = "simple") -> Reranker:
    if configured.startswith("cohere."):
        return CohereRerank(model_id=configured)
    return LocalReranker()
