"""Audit records (NFR-12): actor, action, config/model context, outcome —
persisted locally and emitted to structured logs. Security-relevant actions
(ticket create, ingestion, auth failures, admin ops) must call this."""

import logging
from typing import Any

logger = logging.getLogger("regintel.audit")


def record_audit(
    store,
    actor: str,
    action: str,
    outcome: str,
    detail: dict[str, Any] | None = None,
) -> None:
    """Persist + log one audit record. Never include secrets or payloads
    containing sensitive user data in `detail`."""
    detail = detail or {}
    store.add_audit_record(actor=actor, action=action, outcome=outcome, detail=detail)
    logger.info(
        "audit",
        extra={"actor": actor, "action": f"audit.{action}", "outcome": outcome},
    )
