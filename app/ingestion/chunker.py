"""Contextual chunking (FR-11): split on '##' section headings and attach
document context (title/section) + metadata to every chunk. Pre-heading
text becomes the 'Overview' section."""

import re

from app.ingestion.base import RawDocument
from app.retrieval.corpus import HEADING, Chunk

MIN_CHUNK_CHARS = 20
DOC_TITLE = re.compile(r"^\s*#\s+[^\n]*")


def chunk_document(doc: RawDocument) -> list[Chunk]:
    parts = HEADING.split(doc.body)
    sections = [("Overview", DOC_TITLE.sub("", parts[0]))]
    sections += [(parts[i].strip(), parts[i + 1]) for i in range(1, len(parts) - 1, 2)]

    chunks: list[Chunk] = []
    for idx, (section, text) in enumerate(sections):
        text = " ".join(text.split())
        if len(text) < MIN_CHUNK_CHARS:
            continue
        chunks.append(
            Chunk(
                chunk_id=f"{doc.doc_id}#s{idx}",
                document_id=doc.doc_id,
                title=doc.title,
                section=section,
                text=text,
                department=doc.department,
                acl=doc.acl,
                version=doc.version,
                source_system=doc.source_system,
                source_ref=doc.metadata.get("path", ""),
                source_url=doc.source_url,
            )
        )
    return chunks
