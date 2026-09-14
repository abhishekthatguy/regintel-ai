# Phase 2 — Retrieval & Grounding

**Goal:** replace the local toy retrieval with the real RAG pipeline — ingestion, chunking, embeddings, hybrid search, rerank, full citation contract. Everything still runs locally (OpenSearch via docker / or provisioned serverless).

## End-to-end slice after this phase

An admin runs ingestion from the UI/API → documents flow through a source adapter → contextual chunking → embeddings → hybrid index. The same chat from Phase 1 now answers against a real corpus with reranked evidence, full citation contracts (page/section/excerpt/scores/version), and a golden retrieval eval proving ≥80% top-5 relevance.

## Scope

### Ingestion pipeline (FR-10, FR-11)
- `SourceAdapter` interface: `list_documents()`, `fetch()`, `normalize()` → ship **local filesystem adapter** (used in demo) + **OpenText adapter skeleton** behind config (real API wiring pending OQ-02) + **Graph adapter skeleton**
- Document-aware contextual chunking: split by structure; each chunk carries `doc_id, title, source, page/section, department, acl, version`
- Version/checksum tracking; re-ingestion replaces stale chunks (source-drift mitigation); failed items → dead-letter list + status reporting (NFR-11)
- Ingestion job API: `POST /v1/admin/ingestions` → job ID + status polling

### Indexing & retrieval (FR-12..14)
- `Embedder` interface; implementations: local model (default for offline demo) + Bedrock Titan v2 / Cohere v3 (config-selected)
- OpenSearch (docker locally / Serverless in cloud): vector + keyword index, merge candidates, metadata/ACL filters applied **server-side**
- `Reranker` interface; local cross-encoder default + Cohere Rerank impl; relevance threshold removes weak evidence → Not Found path
- Haiku (or configured small model) for query rewriting / context labels (FR-16)

### Full citation contract (FR-17)
- All fields: `citation_id, document_id, title, source_system, source_url_or_ref, page/section, chunk_id, quoted_excerpt, retrieval_score, rerank_score, document_version, user_access_decision`
- Citation resolution verified in eval (≥95% target)

### Storage
- Local: files under `data/`; enterprise: S3 adapter for raw/normalized docs + artifacts
- Chunk store schema migration; index management scripts

### Evaluator v2
- Golden retrieval set: questions ↔ expected doc/chunk IDs, department owners' eval questions
- Adds: top-5 relevance (≥80%), groundedness (≥4/5), citation correctness (≥95%), completeness (≥4/5)
- Unauthorized-department exclusion cases (pre-test for P3 security)

## Out of scope

Real Entra auth (stub identity still drives ACL filters), DynamoDB/Redis, streaming protocol, Angular.

## Exit criteria

- [ ] Ingestion job runs from UI/API end-to-end; artifacts + chunk index updated; failures dead-lettered
- [ ] Hybrid retrieval + rerank wired via config; evidence threshold drives not-found responses
- [ ] Citations meet full contract; UI renders page/section/excerpt/scores
- [ ] ACL metadata filters provably exclude other-department content
- [ ] Golden eval: retrieval ≥80% top-5, citations ≥95%, groundedness ≥4/5
- [ ] Re-index runbook documented (OQ-03 decision recorded)

## Key risks

- OpenSearch Serverless has minimum cost — keep docker local path as the default demo; cloud index optional/config-gated
- OpenText API uncertainty (OQ-02) — adapter skeleton + interface only; don't block phase on enterprise access
