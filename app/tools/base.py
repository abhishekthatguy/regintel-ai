from dataclasses import dataclass
from typing import Any

from app.schemas.config import UseCaseConfig
from app.schemas.identity import UserContext
from app.stores.sqlite import SQLiteStore


@dataclass
class ToolContext:
    """Everything a tool needs: caller identity, config, stores, retriever.
    Assembled once per use case; nodes derive request-scoped copies — never
    populate `user` from shared state."""

    user: UserContext | None
    usecase: UseCaseConfig
    store: SQLiteStore
    embedder: Any  # Embedder (app.retrieval.embeddings)
    reranker: Any  # Reranker (app.retrieval.rerank)
    crm: Any  # CRMAdapter (app.crm.base)
