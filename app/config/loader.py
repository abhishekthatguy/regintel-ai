import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.schemas.config import UseCaseConfig

logger = logging.getLogger(__name__)


class UseCaseNotFoundError(Exception):
    pass


class ConfigValidationError(Exception):
    pass


class UseCaseLoader:
    """Loads versioned USECASE config from local YAML files.
    Phase 3 swaps the backend to DynamoDB behind this same interface."""

    def __init__(self, usecase_dir: Path):
        self._dir = usecase_dir
        self._cache: dict[str, UseCaseConfig] = {}

    def list_usecases(self) -> list[str]:
        if not self._dir.is_dir():
            return []
        return sorted(p.stem for p in self._dir.glob("*.yaml"))

    def get(self, usecase_id: str) -> UseCaseConfig:
        if usecase_id in self._cache:
            return self._cache[usecase_id]
        path = self._dir / f"{usecase_id}.yaml"
        if not path.is_file():
            raise UseCaseNotFoundError(f"unknown use case: {usecase_id}")
        try:
            raw = yaml.safe_load(path.read_text())
            config = UseCaseConfig.model_validate(raw)
        except ValidationError as exc:
            raise ConfigValidationError(f"invalid use case config {path.name}: {exc}") from exc
        if config.usecase_id != usecase_id:
            raise ConfigValidationError(
                f"usecase_id mismatch: file {path.name} declares {config.usecase_id!r}"
            )
        self._cache[usecase_id] = config
        logger.info(
            "loaded use case config",
            extra={"action": "config_load", "outcome": config.usecase_id},
        )
        return config

    def invalidate(self, usecase_id: str | None = None) -> None:
        if usecase_id:
            self._cache.pop(usecase_id, None)
        else:
            self._cache.clear()
