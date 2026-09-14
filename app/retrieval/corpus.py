import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class Chunk(BaseModel):
    """A retrievable unit of knowledge with source metadata (FR-11 subset)."""

    chunk_id: str
    document_id: str
    title: str
    text: str
    section: str = ""
    department: str = ""
    acl: list[str] = Field(default_factory=list)
    version: str = "1"
    source_system: str = "local_files"
    source_ref: str = ""
    source_url: str = ""


FRONT_MATTER = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
HEADING = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def load_corpus(knowledge_dir: Path) -> list[Chunk]:
    """Load markdown docs with YAML front-matter; chunk by '##' sections.
    Phase 2 replaces this with the ingestion pipeline + OpenSearch."""
    chunks: list[Chunk] = []
    for path in sorted(knowledge_dir.rglob("*.md")):
        raw = path.read_text()
        match = FRONT_MATTER.match(raw)
        meta, body = ({}, raw) if not match else (yaml.safe_load(match.group(1)), match.group(2))

        doc_id = meta.get("doc_id", path.stem)
        title = meta.get("title", path.stem)
        base = {
            "document_id": doc_id,
            "title": title,
            "department": meta.get("department", ""),
            "acl": meta.get("acl", []),
            "version": str(meta.get("version", "1")),
            "source_system": meta.get("source_system", "local_files"),
            "source_ref": str(path.relative_to(knowledge_dir.parent)),
            "source_url": meta.get("source_url", ""),
        }

        # Split into sections on '##' headings; pre-heading text = section "Overview".
        parts = HEADING.split(body)
        sections = [("Overview", parts[0])]
        sections += [(parts[i].strip(), parts[i + 1]) for i in range(1, len(parts) - 1, 2)]

        for idx, (section, text) in enumerate(sections):
            text = " ".join(text.split())
            if len(text) < 20:
                continue
            chunks.append(
                Chunk(chunk_id=f"{doc_id}#s{idx}", section=section, text=text, **base)
            )
    return chunks
