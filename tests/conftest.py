import pytest
from starlette.testclient import TestClient

from app.main import create_app
from app.settings import get_settings
from app.stores.sqlite import SQLiteStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("REGINTEL_DB_PATH", str(tmp_path / "test.db"))
    get_settings.cache_clear()
    SQLiteStore(tmp_path / "test.db").init_schema()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()
