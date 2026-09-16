import asyncio
import json
import sqlite3
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from app.main import create_app
from app.settings import get_settings
from app.stores.sqlite import SQLiteStore

SEED_DIR = Path(__file__).resolve().parent.parent / "data" / "seed"
KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge"


def seed_demo_data(db_path) -> None:
    conn = sqlite3.connect(db_path)
    with conn:
        for e in json.loads((SEED_DIR / "employees.json").read_text()):
            conn.execute(
                "INSERT OR REPLACE INTO employees VALUES (?, ?, ?, ?, ?)",
                (e["employee_id"], e["name"], e["department"], e["email"], json.dumps(e["roles"])),
            )
        for t in json.loads((SEED_DIR / "tickets.json").read_text()):
            conn.execute(
                "INSERT OR REPLACE INTO tickets VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    t["ticket_id"], t["employee_id"], t["category"], t["description"],
                    t["status"], t["priority"], t["created_at"], t["updated_at"],
                ),
            )
    conn.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app.api import deps

    db = tmp_path / "test.db"
    seed = tmp_path / "seed"
    seed.mkdir()
    for f in SEED_DIR.glob("*.json"):
        (seed / f.name).write_text(f.read_text())
    knowledge = tmp_path / "knowledge"
    import shutil

    shutil.copytree(KNOWLEDGE_DIR, knowledge)
    monkeypatch.setenv("REGINTEL_DB_PATH", str(db))
    monkeypatch.setenv("REGINTEL_SEED_DIR", str(seed))
    monkeypatch.setenv("REGINTEL_KNOWLEDGE_DIR", str(knowledge))
    get_settings.cache_clear()
    SQLiteStore(db).init_schema()
    seed_demo_data(db)
    with TestClient(create_app()) as test_client:
        yield test_client

    async def _close_savers() -> None:
        for runner in deps.RUNNERS:
            if runner._saver_ctx is not None:
                await runner._saver_ctx.__aexit__(None, None, None)
                runner._saver_ctx = None

    asyncio.run(_close_savers())
    deps.RUNNERS.clear()
    deps._runner_for.cache_clear()  # type: ignore[attr-defined]
    deps._store_for.cache_clear()  # type: ignore[attr-defined]
    get_settings.cache_clear()


@pytest.fixture
def settings(client):
    return get_settings()


@pytest.fixture
def get_store(client):
    """The same cached store instance the app uses, with corpus ingested
    (mirrors the auto-ingest that happens on first agent request)."""
    from app.api import deps

    settings = get_settings()
    store = deps._store_for(str(settings.db_path))
    deps.ensure_ingested(store, settings.knowledge_dir)
    return store


@pytest.fixture
def auth_headers():
    """e999 carries the 'admin' role in the stub identity provider."""
    return {"X-Demo-Employee": "e999"}
