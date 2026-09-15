import json
from pathlib import Path
from typing import Any


class LocalCRMAdapter:
    """Demo CRM backed by data/seed/crm_cases.json — the stand-in a real
    Salesforce/Dynamics adapter replaces without touching the graph."""

    def __init__(self, seed_path: Path):
        self._cases = json.loads(seed_path.read_text()) if seed_path.exists() else []

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        cid = case_id.upper()
        return next((c for c in self._cases if c["case_id"].upper() == cid), None)

    def list_cases(self, owner: str, limit: int = 10) -> list[dict[str, Any]]:
        return [c for c in self._cases if c.get("owner") == owner][:limit]
