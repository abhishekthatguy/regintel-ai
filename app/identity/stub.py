import logging

from app.schemas.identity import UserContext

logger = logging.getLogger(__name__)

# Mirrors scripts/seed_db.py — Phase 3 replaces this with Entra ID claims.
DEMO_EMPLOYEES: dict[str, UserContext] = {
    "e001": UserContext(
        employee_id="e001",
        name="Asha Verma",
        department="IT",
        email="asha.verma@example.com",
        roles=["employee"],
        claims={"department": "IT", "auth": "stub"},
    ),
    "e002": UserContext(
        employee_id="e002",
        name="Rahul Nair",
        department="HR",
        email="rahul.nair@example.com",
        roles=["employee"],
        claims={"department": "HR", "auth": "stub"},
    ),
    "e999": UserContext(
        employee_id="e999",
        name="Admin Demo",
        department="IT",
        email="admin@example.com",
        roles=["employee", "admin"],
        claims={"department": "IT", "auth": "stub"},
    ),
}


class StubIdentityProvider:
    """Demo identity: selects a user by employee_id (X-Demo-Employee header).
    Never acceptable beyond local demo — cryptographic JWT validation lands in Phase 3."""

    def __init__(self, default_employee: str = "e001"):
        self._default = default_employee

    async def resolve(
        self, demo_employee: str | None = None, bearer_token: str | None = None
    ) -> UserContext:
        key = demo_employee or self._default
        user = DEMO_EMPLOYEES.get(key, DEMO_EMPLOYEES[self._default])
        logger.debug("resolved stub identity", extra={"actor": user.employee_id})
        return user
