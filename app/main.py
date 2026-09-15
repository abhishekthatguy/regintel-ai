import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_admin import router as admin_router
from app.api.routes_conversations import router as conversations_router
from app.api.routes_health import router as health_router
from app.api.routes_integrations import router as integrations_router
from app.logging_config import configure_logging
from app.middleware import CorrelationIdMiddleware
from app.settings import get_settings
from app.stores.sqlite import SQLiteStore

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    SQLiteStore(settings.db_path).init_schema()
    logger.info("regintel api started", extra={"action": "startup", "outcome": settings.env})
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="RegIntel AI", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(conversations_router)
    app.include_router(admin_router)
    app.include_router(integrations_router)
    return app


app = create_app()
