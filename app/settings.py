from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="REGINTEL_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "local"
    log_level: str = "INFO"
    db_path: Path = PROJECT_ROOT / "data" / "regintel.db"
    usecase_dir: Path = PROJECT_ROOT / "data" / "usecases"
    knowledge_dir: Path = PROJECT_ROOT / "data" / "knowledge"
    default_usecase: str = "it_support"
    default_employee: str = "e001"


@lru_cache
def get_settings() -> Settings:
    return Settings()
