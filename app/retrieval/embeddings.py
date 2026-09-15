"""Embedder implementations (FR-12).

- HashingEmbedder: deterministic feature-hashing vectors, no external calls —
  the local default so the demo and eval suite run offline.
- BedrockEmbedder: Titan Embed v2 / Cohere Embed v3 via Bedrock, enabled by
  config when credentials exist (Phase 3 wiring).
"""

import hashlib
import math
import os
from typing import Protocol

from app.retrieval.bm25 import tokenize


class Embedder(Protocol):
    model_id: str
    dimensions: int

    def embed(self, text: str) -> list[float]: ...


class HashingEmbedder:
    """Deterministic feature-hashing embedding. Captures lexical similarity —
    not semantic — but exercises the real vector-search path locally."""

    model_id = "local-hashing-v1"

    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dimensions
        for token in tokenize(text):
            bucket = int(hashlib.md5(token.encode()).hexdigest(), 16) % self.dimensions
            vec[bucket] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class BedrockEmbedder:
    """Titan Embed v2 / Cohere Embed v3 via Bedrock runtime.
    Requires AWS credentials + region; falls back to HashingEmbedder if
    boto3/Bedrock is unavailable so local demo never breaks (BRD risk:
    model availability by region)."""

    def __init__(self, model_id: str = "amazon.titan-embed-text-v2:0", dimensions: int = 1024):
        self.model_id = model_id
        self.dimensions = dimensions
        self._client = None
        self._fallback = HashingEmbedder(dimensions)
        try:
            import boto3  # noqa: F401

            self._client = boto3.client(
                "bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1")
            )
        except Exception:
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def embed(self, text: str) -> list[float]:
        if not self._client:
            return self._fallback.embed(text)
        import json

        resp = self._client.invoke_model(
            modelId=self.model_id, body=json.dumps({"inputText": text})
        )
        return json.loads(resp["body"].read())["embedding"]


def get_embedder(configured: str = "local") -> Embedder:
    if configured.startswith(("amazon.titan", "cohere.")):
        return BedrockEmbedder(model_id=configured)
    return HashingEmbedder()


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))
