from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, Request

from app.agent.runner import AgentRunner, StubAgentRunner
from app.config.loader import UseCaseLoader
from app.identity.stub import StubIdentityProvider
from app.schemas.identity import UserContext
from app.settings import Settings, get_settings
from app.stores.sqlite import SQLiteStore

DEMO_EMPLOYEE_HEADER = "X-Demo-Employee"


@lru_cache
def _store_for(db_path: str) -> SQLiteStore:
    store = SQLiteStore(db_path)
    store.init_schema()
    return store


def get_store(settings: Annotated[Settings, Depends(get_settings)]) -> SQLiteStore:
    return _store_for(str(settings.db_path))


def get_usecase_loader(settings: Annotated[Settings, Depends(get_settings)]) -> UseCaseLoader:
    return UseCaseLoader(settings.usecase_dir)


def get_agent_runner() -> AgentRunner:
    return StubAgentRunner()


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
