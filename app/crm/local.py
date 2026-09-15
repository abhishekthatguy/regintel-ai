import json
from pathlib import Path
from typing import Any


class LocalCRMAdapter:
    """Demo CRM backed by data/seed/crm_cases.json — the stand-in a real
    Salesforce/Dynamics adapter replaces without touching the graph.
    Writes persist back to the seed file so restarts keep created cases."""

    def __init__(self, seed_path: Path):
        self._path = seed_path
        self._cases = json.loads(seed_path.read_text()) if seed_path.exists() else []

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        cid = case_id.upper()
        return next((c for c in self._cases if c["case_id"].upper() == cid), None)

    def list_cases(self, owner: str, limit: int = 10) -> list[dict[str, Any]]:
        return [c for c in self._cases if c.get("owner") == owner][:limit]

    def find_duplicate_case(self, owner: str, subject: str) -> dict[str, Any] | None:
        key = subject.strip().lower()
        return next(
            (
                c
                for c in self._cases
                if c.get("owner") == owner
                and c.get("status") != "closed"
                and c.get("subject", "").strip().lower() == key
            ),
            None,
        )

    def next_case_id(self) -> str:
        nums = [int(c["case_id"].split("-")[1]) for c in self._cases if c["case_id"].startswith("CASE-")]
        return f"CASE-{(max(nums) if nums else 7000) + 1}"

    def create_case(self, case: dict[str, Any]) -> dict[str, Any]:
        # Idempotent: same (owner, subject) open case is reused, not duplicated.
        existing = self.find_duplicate_case(case["owner"], case["subject"])
        if existing:
            return existing
        self._cases.append(case)
        self._path.write_text(json.dumps(self._cases, indent=2) + "\n")
        return case
