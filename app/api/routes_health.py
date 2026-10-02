from fastapi import APIRouter

from app.api.deps import SettingsDep, StoreDep, UseCaseDep

router = APIRouter(tags=["health"])


@router.get("/")
async def root(settings: SettingsDep) -> dict:
    return {
        "service": "RegIntel AI",
        "version": "0.1.0",
        "env": settings.env,
        "auth_mode": settings.auth_mode,
        "docs": "/docs",
        "health": "/health",
        "ready": "/ready",
    }


@router.get("/health")
async def health(settings: SettingsDep) -> dict:
    return {
        "status": "ok",
        "env": settings.env,
        "version": "0.1.0",
        "auth_mode": settings.auth_mode,
    }


@router.get("/ready")
async def ready(store: StoreDep, loader: UseCaseDep) -> dict:
    checks = {
        "database": store.ping(),
        "usecase_config": bool(loader.list_usecases()),
    }
    return {"ready": all(checks.values()), "checks": checks}
