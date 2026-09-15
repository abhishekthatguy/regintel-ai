from app.ingestion.base import RawDocument


class AdapterNotConfiguredError(Exception):
    pass


class OpenTextAdapter:
    """OpenText (secure information management) source adapter — skeleton.

    Real wiring needs the OpenText product + API confirmed (OQ-02 in
    docs/decisions-and-open-questions.md): Content Server REST API vs
    Extended ECM vs Core Content. The pipeline contract is already fixed:
    list_documents() must yield RawDocument carrying doc_id, version,
    checksum, department and ACL so downstream chunking/ACL filters work
    unchanged."""

    source_id = "opentext"

    def __init__(self, base_url: str = "", token: str = ""):
        self._base_url = base_url
        self._token = token

    def list_documents(self) -> list[RawDocument]:
        raise AdapterNotConfiguredError(
            "OpenText adapter not configured — set base_url/token and confirm "
            "the product API (OQ-02)"
        )
