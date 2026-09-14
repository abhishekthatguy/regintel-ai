from typing import Protocol

from app.schemas.identity import UserContext


class IdentityProvider(Protocol):
    """Resolves a request into an authenticated UserContext.
    Phase 0: stub. Phase 3: Entra ID JWT validation (FR-01)."""

    async def resolve(self, employee_id: str | None) -> UserContext: ...
