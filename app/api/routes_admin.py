from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_identity, get_store
from app.ingestion.graph_source import GraphSourceAdapter
from app.ingestion.local_files import LocalFileAdapter
from app.ingestion.opentext import OpenTextAdapter
from app.ingestion.pipeline import IngestionPipeline
from app.retrieval.embeddings import get_embedder
from app.schemas.identity import UserContext
from app.settings import Settings, get_settings
from app.stores.sqlite import SQLiteStore

router = APIRouter(prefix="/v1/admin", tags=["admin"])


def require_admin(user: Annotated[UserContext, Depends(get_identity)]) -> UserContext:
    if "admin" not in user.roles:
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


class IngestRequest(BaseModel):
    source: Literal["local_files", "opentext", "msgraph"] = "local_files"


def _adapter_for(source: str, settings: Settings):
    if source == "local_files":
        return LocalFileAdapter(settings.knowledge_dir)
    if source == "opentext":
        return OpenTextAdapter()  # skeleton: raises AdapterNotConfiguredError
    return GraphSourceAdapter()


@router.post("/ingestions", status_code=201)
def start_ingestion(
    req: IngestRequest,
    _admin: Annotated[UserContext, Depends(require_admin)],
    store: Annotated[SQLiteStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """FR-10 admin trigger: run an ingestion job for a source adapter.
    Synchronous in the local demo (jobs are seconds); a cloud deploy would
    hand this to a worker."""
    adapter = _adapter_for(req.source, settings)
    pipeline = IngestionPipeline(store, get_embedder())
    try:
        result = pipeline.run(adapter)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Source adapter failed: {exc}") from exc
    from app.audit import record_audit

    record_audit(
        store,
        actor=_admin.employee_id,
        action="ingestion_run",
        outcome=result["job_id"],
        detail={"source": req.source, "ingested": result["ingested"], "failed": result["failed"]},
    )
    return result


@router.get("/ingestions")
def list_ingestions(
    _admin: Annotated[UserContext, Depends(require_admin)],
    store: Annotated[SQLiteStore, Depends(get_store)],
) -> dict:
    return {"jobs": store.list_ingestion_jobs()}


@router.get("/ingestions/{job_id}")
def get_ingestion(
    job_id: str,
    _admin: Annotated[UserContext, Depends(require_admin)],
    store: Annotated[SQLiteStore, Depends(get_store)],
) -> dict:
    job = store.get_ingestion_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    job["failures"] = store.ingestion_failures(job_id)
    return job


@router.get("/analytics")
def analytics(
    _admin: Annotated[UserContext, Depends(require_admin)],
    store: Annotated[SQLiteStore, Depends(get_store)],
) -> dict:
    """FR-25: usage/quality/feedback/latency/not-found aggregates for the
    dashboard — sliced by use case and day; department scoping rides on the
    admin's own claims in cloud mode."""
    return {
        "summary": store.analytics_summary(),
        "by_usecase": store.analytics_by_usecase(),
        "daily": store.analytics_daily(),
        "not_found_queries": store.analytics_not_found(),
        "recent_feedback": store.analytics_feedback_recent(),
        "audit_recent": store.list_audit_records(limit=20),
    }
