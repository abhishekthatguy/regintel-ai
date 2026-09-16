"""Phase 2: ingestion pipeline, hybrid retrieval, citation contract, admin API."""

import pytest

from app.ingestion.base import RawDocument
from app.ingestion.chunker import chunk_document
from app.ingestion.local_files import LocalFileAdapter
from app.ingestion.opentext import AdapterNotConfiguredError, OpenTextAdapter
from app.ingestion.pipeline import IngestionPipeline
from app.retrieval.embeddings import HashingEmbedder, get_embedder
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.rerank import get_reranker


@pytest.fixture
def retriever(get_store):
    store = get_store
    return HybridRetriever(
        store.all_chunks(), store.chunk_vectors(), HashingEmbedder(), get_reranker()
    )


# --- ingestion pipeline ---------------------------------------------------


def test_ingestion_populates_chunks_vectors_checksums(get_store):
    store = get_store
    assert len(store.all_chunks()) == 101
    vectors = store.chunk_vectors()
    assert len(vectors) == 101
    assert all(len(v) == 384 for v in vectors.values())
    assert store.document_checksum("KB-IT-001")


def test_reingestion_skips_unchanged_docs(get_store, settings):
    store = get_store
    result = IngestionPipeline(store, get_embedder()).run(
        LocalFileAdapter(settings.knowledge_dir)
    )
    assert result["ingested"] == 0  # all checksums unchanged


def test_checksum_change_triggers_reindex(get_store, tmp_path):
    store = get_store
    # A single modified doc re-ingests; everything else skips.
    doc_md = tmp_path / "doc.md"
    doc_md.write_text(
        "---\ndoc_id: KB-T-1\ntitle: Test Doc\ndepartment: IT\nacl: [IT]\nversion: '1'\n---\n"
        "## Body\nOriginal text about ldap bind failures.\n"
    )

    class OneDoc:
        source_id = "test"

        def list_documents(self):
            return LocalFileAdapter(tmp_path).list_documents()

    r1 = IngestionPipeline(store, get_embedder()).run(OneDoc())
    assert r1["ingested"] == 1
    doc_md.write_text(doc_md.read_text().replace("Original", "Updated"))
    r2 = IngestionPipeline(store, get_embedder()).run(OneDoc())
    assert r2["ingested"] == 1
    assert any("Updated text" in c.text for c in store.all_chunks())


def test_ingestion_failure_goes_to_dlq(get_store):
    store = get_store

    class BadAdapter:
        source_id = "bad"

        def list_documents(self):
            good = RawDocument(
                doc_id="KB-OK", title="OK", body="## S\nsome long enough body text here.",
                department="IT", acl=["IT"], source_system="bad", checksum="a1",
            )
            bad = RawDocument(
                doc_id="KB-BAD", title="Bad", body="## S\nshort",
                department="IT", acl=["IT"], source_system="bad", checksum="b2",
            )
            return [good, bad]

    # KB-BAD produces zero chunks -> not a failure; force a real failure by
    # corrupting after chunking is impossible here, so use an adapter error path:
    class FailingAdapter:
        source_id = "failing"

        def list_documents(self):
            raise RuntimeError("source unreachable")

    with pytest.raises(RuntimeError):
        IngestionPipeline(store, get_embedder()).run(FailingAdapter())
    job = store.list_ingestion_jobs()[0]
    assert job["status"] == "failed"
    assert "source unreachable" in job["error"]


def test_per_doc_failure_recorded_in_dlq(get_store):
    store = get_store
    import app.ingestion.pipeline as pipeline_mod

    original = pipeline_mod.chunk_document

    def flaky(doc):
        if doc.doc_id == "KB-BOOM":
            raise ValueError("corrupt document")
        return original(doc)

    class TwoDocs:
        source_id = "test"

        def list_documents(self):
            return [
                RawDocument(doc_id="KB-BOOM", title="Boom", body="x" * 50,
                            source_system="t", checksum="c1"),
                RawDocument(doc_id="KB-FINE", title="Fine",
                            body="## S\n" + "fine body " * 10,
                            source_system="t", checksum="c2"),
            ]

    pipeline_mod.chunk_document = flaky
    try:
        result = IngestionPipeline(store, get_embedder()).run(TwoDocs())
    finally:
        pipeline_mod.chunk_document = original

    assert result["failed"] == 1 and result["ingested"] == 1
    job = store.get_ingestion_job(result["job_id"])
    assert job["status"] == "completed_with_failures"
    failures = store.ingestion_failures(result["job_id"])
    assert failures[0]["doc_id"] == "KB-BOOM"
    assert "corrupt" in failures[0]["error"]


def test_chunker_contextual_sections():
    doc = RawDocument(
        doc_id="D1", title="Doc", body="Intro text that is long enough to chunk.\n"
        "## Install\nInstall steps here with enough text.\n## Verify\nVerify steps here too.",
        source_system="t",
    )
    chunks = chunk_document(doc)
    assert {c.section for c in chunks} == {"Overview", "Install", "Verify"}
    assert all(c.document_id == "D1" for c in chunks)


# --- hybrid retrieval -----------------------------------------------------


def test_hybrid_retrieval_returns_both_scores(retriever):
    evidence = retriever.retrieve("VPN setup instructions", allowed_departments={"IT"}, top_k=3)
    assert evidence
    for item in evidence:
        assert item["retrieval_score"] > 0
        assert item["rerank_score"] is not None


def test_vector_leg_enforces_acl(retriever):
    """KB-IT-008 (Admin rights, ACL=[IT]) must never surface for HR."""
    hr = retriever.retrieve("admin rights local admin laptop", allowed_departments={"HR"}, top_k=10)
    assert all(item["chunk"]["document_id"] != "KB-IT-008" for item in hr)
    it = retriever.retrieve("admin rights local admin laptop", allowed_departments={"IT"}, top_k=10)
    assert any(item["chunk"]["document_id"] == "KB-IT-008" for item in it)


def test_semanticish_query_still_retrieves(retriever):
    """Hybrid vector leg should help even when keywords partially match."""
    evidence = retriever.retrieve("forgotten credentials cannot sign in", allowed_departments={"IT"})
    assert evidence


def test_unconfigured_adapters_fail_closed():
    with pytest.raises(AdapterNotConfiguredError):
        OpenTextAdapter().list_documents()


# --- admin API ------------------------------------------------------------


def test_admin_ingestion_requires_admin_role(client, auth_headers):
    r = client.post("/v1/admin/ingestions", json={"source": "local_files"})
    assert r.status_code == 403  # e001 is employee-only
    r = client.post("/v1/admin/ingestions", json={"source": "local_files"}, headers=auth_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["job_id"].startswith("job-")


def test_admin_ingestion_status_and_404(client, auth_headers):
    r = client.post("/v1/admin/ingestions", json={}, headers=auth_headers)
    job_id = r.json()["job_id"]
    job = client.get(f"/v1/admin/ingestions/{job_id}", headers=auth_headers).json()
    assert job["status"] in ("completed", "completed_with_failures")
    assert "failures" in job
    assert client.get("/v1/admin/ingestions/job-nope", headers=auth_headers).status_code == 404


def test_admin_opentext_source_returns_502(client, auth_headers):
    r = client.post("/v1/admin/ingestions", json={"source": "opentext"}, headers=auth_headers)
    assert r.status_code == 502


# --- citation contract via API --------------------------------------------


def _collect_stream(client, conv_id: str, content: str, headers: dict) -> dict:
    import json

    citations, text = [], ""
    with client.stream(
        "POST",
        f"/v1/conversations/{conv_id}/messages:stream",
        json={"content": content},
        headers=headers,
    ) as resp:
        for line in resp.iter_lines():
            if not line:
                continue
            ev = json.loads(line)
            if ev["type"] == "citation":
                citations.append(ev["data"])
            elif ev["type"] == "token":
                text += ev["data"]["text"]
    return {"citations": citations, "text": text}


def test_citation_contract_fields(client, auth_headers):
    conv = client.post(
        "/v1/conversations", json={"usecase_id": "it_support"}, headers=auth_headers
    ).json()["conversation_id"]
    r = _collect_stream(client, conv, "how do I set up the corporate VPN?", auth_headers)
    assert r["citations"]
    for c in r["citations"]:
        for field in (
            "citation_id", "document_id", "title", "source_system", "source_ref",
            "page_section", "chunk_id", "excerpt", "retrieval_score",
            "rerank_score", "document_version",
        ):
            assert c[field] is not None, f"missing {field} in {c}"
        assert c["access_granted"] is True
