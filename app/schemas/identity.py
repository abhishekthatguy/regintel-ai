from typing import Any

from pydantic import BaseModel, Field


class UserContext(BaseModel):
    """Authenticated principal. In Phase 0 produced by the stub provider;
    in Phase 3 populated from validated Entra ID JWT claims."""

    employee_id: str
    name: str
    department: str
    email: str | None = None
    roles: list[str] = Field(default_factory=list)
    claims: dict[str, Any] = Field(default_factory=dict)
