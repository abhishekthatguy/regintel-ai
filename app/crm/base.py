from typing import Any, Protocol


class CRMAdapter(Protocol):
    """CRM integration boundary (FR-24). Approved read tools today; write
    tools reuse the ticket safety contract (validation → duplicates →
    explicit confirmation → idempotency → audit). Real CRM target TBD (OQ-04)
    — Salesforce/Dynamics adapters implement this same surface."""

    def get_case(self, case_id: str) -> dict[str, Any] | None: ...
    def list_cases(self, owner: str, limit: int = 10) -> list[dict[str, Any]]: ...
