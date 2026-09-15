"""CX integration endpoints (Phase 5). Authenticated like every other route —
a Genesys data action would call these with an OAuth client-credentials JWT."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_identity, get_store, get_usecase_loader
from app.integrations.genesys import suggest
from app.retrieval.embeddings import get_embedder
from app.retrieval.rerank import get_reranker
from app.schemas.identity import UserContext
from app.settings import Settings, get_settings
from app.stores.sqlite import SQLiteStore
from app.tools.base import ToolContext

router = APIRouter(prefix="/v1/integrations", tags=["integrations"])


class SuggestRequest(BaseModel):
    utterance: str = Field(min_length=1, max_length=4000)
    usecase_id: str = "it_support"


@router.post("/genesys/suggest")
def genesys_suggest(
    req: SuggestRequest,
    user: Annotated[UserContext, Depends(get_identity)],
    store: Annotated[SQLiteStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
    loader: Annotated[Any, Depends(get_usecase_loader)],
) -> dict:
    """Agent-assist suggestion: utterance → grounded suggestion + citations.
    Stateless — no conversation row created."""
    usecase = loader.get(req.usecase_id)
    ctx = ToolContext(
        user=user,
        usecase=usecase,
        store=store,
        embedder=get_embedder(usecase.models.embedding),
        reranker=get_reranker(usecase.models.rerank),
        crm=None,
    )
    return suggest(ctx, req.utterance)
