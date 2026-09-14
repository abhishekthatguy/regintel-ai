from dataclasses import dataclass

from app.retrieval.bm25 import BM25Index
from app.schemas.config import UseCaseConfig
from app.schemas.identity import UserContext
from app.stores.sqlite import SQLiteStore


@dataclass
class ToolContext:
    """Everything a tool needs: caller identity, config, stores, indexes.
    Assembled once per request by the runner — never from user input."""

    user: UserContext
    usecase: UseCaseConfig
    store: SQLiteStore
    index: BM25Index
