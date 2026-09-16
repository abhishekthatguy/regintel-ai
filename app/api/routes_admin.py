from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_identity, get_store, get_usecase_loader
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


class KnowledgeUploadRequest(BaseModel):
    filename: str
    content: str


@router.post("/knowledge", status_code=201)
def upload_knowledge(
    req: KnowledgeUploadRequest,
    admin: Annotated[UserContext, Depends(require_admin)],
    store: Annotated[SQLiteStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Department-owner self-service (FR-10/FR-27): upload one markdown doc
    with front-matter → validated → lands in the corpus → re-ingested.
    Checksum drift detection makes the run incremental."""
    import re

    import yaml

    from app.retrieval.corpus import FRONT_MATTER

    if not req.filename.endswith(".md") or "/" in req.filename or ".." in req.filename:
        raise HTTPException(status_code=422, detail="filename must be a plain .md name")
    match = FRONT_MATTER.match(req.content)
    if not match:
        raise HTTPException(status_code=422, detail="missing YAML front-matter")
    meta = yaml.safe_load(match.group(1))
    missing = [f for f in ("doc_id", "title", "department", "acl") if not meta.get(f)]
    if missing:
        raise HTTPException(status_code=422, detail=f"front-matter missing: {missing}")
    if not re.fullmatch(r"KB-[A-Z]+-\d+", str(meta["doc_id"])):
        raise HTTPException(status_code=422, detail="doc_id must match KB-DEPT-NNN")
    if not isinstance(meta["acl"], list) or not meta["acl"]:
        raise HTTPException(status_code=422, detail="acl must be a non-empty list")

    dept_dir = settings.knowledge_dir / str(meta["department"]).lower()
    dept_dir.mkdir(parents=True, exist_ok=True)
    (dept_dir / req.filename).write_text(req.content)

    pipeline = IngestionPipeline(store, get_embedder())
    result = pipeline.run(LocalFileAdapter(settings.knowledge_dir))
    from app.audit import record_audit

    record_audit(
        store,
        actor=admin.employee_id,
        action="knowledge_upload",
        outcome=str(meta["doc_id"]),
        detail={"filename": req.filename, "department": meta["department"], "ingested": result["ingested"]},
    )
    return {"doc_id": meta["doc_id"], "path": str(dept_dir / req.filename), "ingestion": result}


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
        "by_department": store.analytics_by_department(),
        "funnel": store.analytics_funnel(),
        "unmet_needs": store.analytics_unmet_needs(),
        "daily": store.analytics_daily(),
        "not_found_queries": store.analytics_not_found(),
        "recent_feedback": store.analytics_feedback_recent(),
        "audit_recent": store.list_audit_records(limit=20),
    }


@router.get("/usecases")
def list_usecases(
    _admin: Annotated[UserContext, Depends(require_admin)],
    loader: Annotated[Any, Depends(get_usecase_loader)],
) -> dict:
    """Department-owner self-service: every configured use case with its
    department, tools, guardrails, and access rules."""
    return {
        "usecases": [
            {
                "usecase_id": c.usecase_id,
                "name": c.name,
                "department": c.department,
                "version": c.version,
                "tools": [
                    {"name": t.name, "enabled": t.enabled} for t in c.tools
                ],
                "filters": {"department": c.filters.department},
                "guardrails": {
                    "input_checks": c.guardrails.input_checks,
                    "output_checks": c.guardrails.output_checks,
                },
            }
            for c in (loader.get(u) for u in loader.list_usecases())
        ]
    }


@router.get("/usecases/{usecase_id}")
def usecase_detail(
    usecase_id: str,
    _admin: Annotated[UserContext, Depends(require_admin)],
    store: Annotated[SQLiteStore, Depends(get_store)],
    loader: Annotated[Any, Depends(get_usecase_loader)],
) -> dict:
    """One use case's full config + its department's indexed documents + usage."""
    try:
        config = loader.get(usecase_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "config": config.model_dump(mode="json"),
        "documents": store.department_documents(config.filters.department or config.department),
        "usage": store.usecase_usage(usecase_id),
    }
