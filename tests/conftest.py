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
    monkeypatch.setenv("REGINTEL_DB_PATH", str(db))
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
