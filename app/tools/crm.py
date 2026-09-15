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
