from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Header, Request

from app.agent.graph import LangGraphRunner
from app.agent.runner import AgentRunner
from app.config.loader import UseCaseLoader
from app.identity.stub import StubIdentityProvider
from app.ingestion.local_files import LocalFileAdapter
from app.ingestion.pipeline import IngestionPipeline
from app.llm.factory import get_chat_model
from app.retrieval.embeddings import get_embedder
from app.retrieval.rerank import get_reranker
from app.schemas.identity import UserContext
from app.settings import Settings, get_settings
from app.stores.sqlite import SQLiteStore
from app.tools.base import ToolContext

DEMO_EMPLOYEE_HEADER = "X-Demo-Employee"


@lru_cache
def _store_for(db_path: str) -> SQLiteStore:
    store = SQLiteStore(db_path)
    store.init_schema()
    return store


def ensure_ingested(store: SQLiteStore, knowledge_dir: Path) -> None:
    """Auto-ingest the local corpus on first run so the demo works out of
    the box. Explicit re-ingestion goes through POST /v1/admin/ingestions."""
    if not store.all_chunks():
        IngestionPipeline(store, get_embedder()).run(LocalFileAdapter(knowledge_dir))


# Registry of live runners so tests/teardown can close checkpointer connections.
RUNNERS: list[LangGraphRunner] = []


@lru_cache
def _runner_for(db_path: str, knowledge_dir: str) -> LangGraphRunner:
    store = _store_for(db_path)
    ensure_ingested(store, Path(knowledge_dir))

    def ctx_factory(usecase) -> ToolContext:
        return ToolContext(
            user=None,
            usecase=usecase,
            store=store,
            embedder=get_embedder(usecase.models.embedding),
            reranker=get_reranker(usecase.models.rerank),
        )

    runner = LangGraphRunner(ctx_factory, get_chat_model(), db_path)
    RUNNERS.append(runner)
    return runner


def get_store(settings: Annotated[Settings, Depends(get_settings)]) -> SQLiteStore:
    return _store_for(str(settings.db_path))


def get_usecase_loader(settings: Annotated[Settings, Depends(get_settings)]) -> UseCaseLoader:
    return UseCaseLoader(settings.usecase_dir)


def get_agent_runner(settings: Annotated[Settings, Depends(get_settings)]) -> AgentRunner:
    return _runner_for(str(settings.db_path), str(settings.knowledge_dir))


async def get_identity(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    x_demo_employee: Annotated[str | None, Header(alias=DEMO_EMPLOYEE_HEADER)] = None,
) -> UserContext:
    provider = StubIdentityProvider(default_employee=settings.default_employee)
    return await provider.resolve(x_demo_employee)


StoreDep = Annotated[SQLiteStore, Depends(get_store)]
UseCaseDep = Annotated[UseCaseLoader, Depends(get_usecase_loader)]
RunnerDep = Annotated[AgentRunner, Depends(get_agent_runner)]
IdentityDep = Annotated[UserContext, Depends(get_identity)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
