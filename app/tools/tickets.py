from datetime import UTC, datetime

from app.tools.base import ToolContext

CATEGORIES = {"vpn", "hardware", "software", "access", "network", "email", "account", "other"}
PRIORITIES = {"low", "medium", "high", "urgent"}
REQUIRED_FIELDS = ["category", "description"]


class TicketLookupTool:
    """FR-08: return only the authenticated employee's tickets; never invent."""

    name = "ticket_lookup"

    def run(self, ctx: ToolContext, open_only: bool = False) -> dict:
        tickets = ctx.store.list_tickets(ctx.user.employee_id, open_only=open_only)
        return {
            "found": bool(tickets),
            "tickets": [
                {
                    "ticket_id": t["ticket_id"],
                    "category": t["category"],
                    "description": t["description"],
                    "status": t["status"],
                    "priority": t["priority"],
                    "created_at": t["created_at"],
                }
                for t in tickets
            ],
        }


def validate_fields(fields: dict) -> tuple[dict, list[str]]:
    """Normalize + validate collected fields. Returns (clean, missing)."""
    clean = dict(fields)
    if "category" in clean:
        clean["category"] = str(clean["category"]).lower().strip()
        if clean["category"] not in CATEGORIES:
            clean.pop("category")
    if "priority" in clean:
        clean["priority"] = str(clean["priority"]).lower().strip()
        if clean["priority"] not in PRIORITIES:
            clean["priority"] = "medium"
    if "description" in clean:
        clean["description"] = str(clean["description"]).strip(" .:-")
        # Require a substantive description, not just "wifi issues".
        if len(clean["description"]) < 15:
            clean.pop("description")
    missing = [f for f in REQUIRED_FIELDS if f not in clean]
    return clean, missing


class TicketCreateTool:
    """FR-09: validated fields + duplicate check happen in graph nodes;
    this tool only performs the final idempotent persist + audit."""

    name = "ticket_create"

    def run(self, ctx: ToolContext, fields: dict, idempotency_key: str) -> dict:
        now = datetime.now(UTC).isoformat()
        ticket = {
            "ticket_id": ctx.store.next_ticket_id(),
            "employee_id": ctx.user.employee_id,
            "category": fields["category"],
            "description": fields["description"],
            "status": "open",
            "priority": fields.get("priority", "medium"),
            "created_at": now,
            "updated_at": now,
        }
        ctx.store.create_ticket(ticket)
        return {"created": True, "ticket": ticket, "idempotency_key": idempotency_key}
