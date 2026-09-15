from typing import Any, Protocol

from pydantic import BaseModel, Field


class RawDocument(BaseModel):
    """A normalized document from any source system (FR-10/FR-11 input)."""

    doc_id: str
    title: str
    body: str
    department: str = ""
    acl: list[str] = Field(default_factory=list)
    version: str = "1"
    source_system: str
    source_url: str = ""
    checksum: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceAdapter(Protocol):
    """Replaceable document source (FR-10). Implementations: local files
    (demo), OpenText, Microsoft Graph. Adapters only enumerate + fetch;
    chunking/embedding/indexing happen in the pipeline."""

    source_id: str

    def list_documents(self) -> list[RawDocument]:
        """Return normalized documents with metadata. Raises per-doc errors
        are captured by the pipeline into the dead-letter list."""
        ...
