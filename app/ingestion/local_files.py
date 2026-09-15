import hashlib
from pathlib import Path

import yaml

from app.ingestion.base import RawDocument
from app.retrieval.corpus import FRONT_MATTER


class LocalFileAdapter:
    """Reads markdown docs (with YAML front-matter) from data/knowledge/.
    This is the demo source; the interface matches enterprise adapters."""

    source_id = "local_files"

    def __init__(self, knowledge_dir: Path):
        self._dir = knowledge_dir

    def list_documents(self) -> list[RawDocument]:
        docs = []
        for path in sorted(self._dir.rglob("*.md")):
            raw = path.read_text()
            match = FRONT_MATTER.match(raw)
            meta, body = ({}, raw) if not match else (yaml.safe_load(match.group(1)), match.group(2))
            docs.append(
                RawDocument(
                    doc_id=meta.get("doc_id", path.stem),
                    title=meta.get("title", path.stem),
                    body=body,
                    department=meta.get("department", ""),
                    acl=meta.get("acl", []),
                    version=str(meta.get("version", "1")),
                    source_system="local_files",
                    source_url=meta.get("source_url", ""),
                    checksum=hashlib.sha256(raw.encode()).hexdigest(),
                    metadata={"path": str(path.relative_to(self._dir.parent))},
                )
            )
        return docs
