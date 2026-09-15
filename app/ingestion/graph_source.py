from app.ingestion.base import RawDocument
from app.ingestion.opentext import AdapterNotConfiguredError


class GraphSourceAdapter:
    """Microsoft Graph document source adapter — skeleton.

    Real wiring (Phase 3): app registration with Sites.ReadAll/Files.Read
    permissions, client-credentials token via Entra ID, enumerate drive
    items, map site/library metadata to department + ACL fields."""

    source_id = "msgraph"

    def __init__(self, tenant_id: str = "", client_id: str = "", client_secret: str = ""):
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret

    def list_documents(self) -> list[RawDocument]:
        raise AdapterNotConfiguredError(
            "Graph adapter not configured — needs tenant_id/client_id/secret "
            "and Entra app registration (Phase 3 dependency)"
        )
