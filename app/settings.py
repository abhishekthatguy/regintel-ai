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
    seed_dir: Path = PROJECT_ROOT / "data" / "seed"

    # --- Phase 3: auth / cloud backend switches ---
    # "stub" keeps the X-Demo-Employee header path; "jwt" requires a Bearer
    # token validated for signature/issuer/audience/expiry on every request.
    auth_mode: str = "stub"
    jwt_issuer: str = "regintel-dev"
    jwt_audience: str = "regintel-api"
    jwt_secret: str = ""  # HS256 dev key — never a real secret in repo/.env.example
    jwt_jwks_url: str = ""  # Entra JWKS endpoint when set (RS256)

    # Backend selection — enterprise implementations swap in via config.
    store_backend: str = "sqlite"  # "dynamodb" -> DynamoDBStore (needs AWS cfg)
    cache_backend: str = "local"  # "redis" -> RedisCache (needs redis_url)
    redis_url: str = ""
    cache_ttl_seconds: int = 300
    guardrail_id: str = ""  # Bedrock guardrail id/version, e.g. "abc123:1"

    # Browser clients allowed to call the API (Angular dev server, etc.).
    allowed_origins: list[str] = [
        "http://localhost:4200",
        "http://localhost:8501",
        "http://127.0.0.1:4200",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
