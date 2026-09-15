import pytest

from app.config.loader import (
    ConfigValidationError,
    UseCaseLoader,
    UseCaseNotFoundError,
)
from app.settings import get_settings


@pytest.fixture
def loader():
    return UseCaseLoader(get_settings().usecase_dir)


def test_lists_all_usecases(loader):
    assert loader.list_usecases() == ["finance_support", "hr_support", "it_support"]


def test_loads_it_support(loader):
    config = loader.get("it_support")
    assert config.usecase_id == "it_support"
    assert config.department == "IT"
    assert config.enabled_tools() == [
        "knowledge_search",
        "ticket_lookup",
        "ticket_create",
        "crm_lookup",
        "crm_case_create",
    ]


def test_finance_usecase_loads(loader):
    config = loader.get("finance_support")
    assert config.department == "Finance"
    assert "crm_lookup" in config.enabled_tools()


def test_hr_has_ticket_tools_disabled(loader):
    config = loader.get("hr_support")
    assert config.enabled_tools() == ["knowledge_search"]


def test_unknown_usecase_raises(loader):
    with pytest.raises(UseCaseNotFoundError):
        loader.get("nonexistent")


def test_invalid_config_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("usecase_id: bad\nversion: not-a-number\n")
    loader = UseCaseLoader(tmp_path)
    with pytest.raises(ConfigValidationError):
        loader.get("bad")


def test_id_mismatch_raises(tmp_path):
    bad = tmp_path / "wrong.yaml"
    bad.write_text("usecase_id: different\nname: Mismatch\n")
    loader = UseCaseLoader(tmp_path)
    with pytest.raises(ConfigValidationError):
        loader.get("wrong")
