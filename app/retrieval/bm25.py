import math
import re
from collections import Counter

from app.retrieval.corpus import Chunk

TOKEN = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "a", "an", "the", "is", "are", "to", "of", "in", "for", "on", "and", "or",
    "i", "my", "me", "do", "how", "what", "can", "it", "your", "you", "we",
}


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOPWORDS]


class BM25Index:
    """Minimal BM25 over in-memory chunks. Phase 2 swaps to OpenSearch hybrid
    behind the same search() contract."""

    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self._k1, self._b = k1, b
        self._chunks = chunks
        self._tf = [Counter(tokenize(f"{c.title} {c.section} {c.text}")) for c in chunks]
        self._dl = [sum(tf.values()) for tf in self._tf]
        self._avgdl = sum(self._dl) / len(self._dl) if self._dl else 1.0
        df: Counter[str] = Counter()
        for tf in self._tf:
            df.update(tf.keys())
        n = len(chunks)
        self._idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(
        self,
        query: str,
        top_k: int = 5,
        allowed_departments: set[str] | None = None,
    ) -> list[tuple[Chunk, float]]:
        """Return (chunk, score) ranked. ACL: a chunk is visible if 'ALL' is in
        its acl or its department is allowed (FR-02 server-side filter)."""
        terms = tokenize(query)
        scores: list[tuple[Chunk, float]] = []
        for chunk, tf, dl in zip(self._chunks, self._tf, self._dl, strict=True):
            if allowed_departments is not None and "ALL" not in chunk.acl:
                if chunk.department not in allowed_departments:
                    continue
            score = 0.0
            for term in terms:
                f = tf.get(term, 0)
                if f == 0:
                    continue
                idf = self._idf.get(term, 0.0)
                denom = f + self._k1 * (1 - self._b + self._b * dl / self._avgdl)
                score += idf * (f * (self._k1 + 1)) / denom
            if score > 0:
                scores.append((chunk, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
