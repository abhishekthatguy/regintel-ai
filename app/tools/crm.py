import re

from app.tools.base import ToolContext

CASE_ID_RE = re.compile(r"\bCASE-?(\d{3,})\b", re.IGNORECASE)


class CRMLookupTool:
    """FR-24 read path: CRM case lookup via the configured CRMAdapter.
    Same server-side scoping as ticket tools — callers only see their own
    cases. Write tools land behind the ticket safety contract later."""

    name = "crm_lookup"

    def run(self, ctx: ToolContext, query: str) -> dict:
        match = CASE_ID_RE.search(query)
        if match:
            case = ctx.crm.get_case(f"CASE-{match.group(1)}")
            # Ownership scoping — no cross-employee case reads.
            if case is None or case.get("owner") != ctx.user.employee_id:
                return {"found": False, "cases": []}
            return {"found": True, "cases": [case]}
        cases = ctx.crm.list_cases(ctx.user.employee_id)
        return {"found": bool(cases), "cases": cases}


CASE_REQUIRED_FIELDS = ["subject", "description"]


def validate_case_fields(fields: dict) -> tuple[dict, list[str]]:
    """Normalize + validate CRM case fields. Returns (clean, missing)."""
    clean = dict(fields)
    if "subject" in clean:
        clean["subject"] = str(clean["subject"]).strip(" .:-")
        if len(clean["subject"]) < 8:
            clean.pop("subject")
    if "description" in clean:
        clean["description"] = str(clean["description"]).strip(" .:-")
        if len(clean["description"]) < 15:
            clean.pop("description")
    if "priority" in clean:
        clean["priority"] = str(clean["priority"]).lower().strip()
        if clean["priority"] not in {"low", "medium", "high", "urgent"}:
            clean["priority"] = "medium"
    missing = [f for f in CASE_REQUIRED_FIELDS if f not in clean]
    return clean, missing


class CRMCaseCreateTool:
    """FR-24 write path: same safety contract as ticket_create — the graph
    validates, checks duplicates, and requires explicit confirmation; this
    tool performs the final idempotent write. Audit lands in the node."""

    name = "crm_case_create"

    def run(self, ctx: ToolContext, fields: dict, idempotency_key: str) -> dict:
        from datetime import UTC, datetime

        now = datetime.now(UTC).isoformat()
        case = {
            "case_id": ctx.crm.next_case_id(),
            "owner": ctx.user.employee_id,
            "subject": fields["subject"],
            "description": fields["description"],
            "status": "open",
            "priority": fields.get("priority", "medium"),
            "account": fields.get("account", "Internal"),
            "updated_at": now,
        }
        created = ctx.crm.create_case(case)
        return {
            "created": created["case_id"] == case["case_id"],
            "case": created,
            "idempotency_key": idempotency_key,
        }
