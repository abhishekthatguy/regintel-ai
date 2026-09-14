from fastapi import APIRouter

from app.api.deps import SettingsDep, StoreDep, UseCaseDep

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(settings: SettingsDep) -> dict:
    return {"status": "ok", "env": settings.env, "version": "0.1.0"}


@router.get("/ready")
async def ready(store: StoreDep, loader: UseCaseDep) -> dict:
    checks = {
        "database": store.ping(),
        "usecase_config": bool(loader.list_usecases()),
    }
    return {"ready": all(checks.values()), "checks": checks}
