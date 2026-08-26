## Context

The ITSO evaluator currently receives deterministic local citation/reference prechecks, the ITSO rubric, and SLM-derived chunks. It has no authoritative local policy evidence for ownership, privacy, or rights; its DOI signals also cannot establish whether a DOI resolves to a registered work. The evaluator must remain advisory, preserve local data residency, and never send SLM text to an external service.

The existing Reference Library manages local syllabus and curriculum assets, and the existing `agent_results.provenance` contract records bounded evidence snapshots. The current FastAPI process uses synchronous clients and a parallel supervisor, so any new pre-dispatch tool must be bounded and non-fatal.

## Goals / Non-Goals

**Goals:**
- Let admins ingest and manage authoritative policy PDFs for ITSO evidence.
- Store policy chunks in a dedicated local Chroma collection and retrieve criterion-targeted clauses.
- Preserve bounded, auditable policy-evidence outcomes in ITSO provenance.
- Make unavailable policy evidence explicit but non-punitive.

**Non-Goals:**
- Detect or prove plagiarism, academic misconduct, legal violations, or reference correctness.
- Send SLM text, citation text, student data, raw prompts, or uploaded documents to an external provider.
- Add source-title fuzzy matching, title/author search, DOI verification, OpenAlex/Exa fallback, or general web search.
- Ship legal/policy content with EquipED; administrators must upload authoritative documents.
- Change the human-review-authoritative status of evaluation results.

## Decisions

### 1. Policy PDFs are a new admin-only local source type

Add `policy` as a document source type with an explicit `policy_area` classification: `intellectual_property`, `data_privacy`, `academic_rights`, or `general_itso`. The `Document` record remains the source of truth. `policy_area` is nullable only for non-policy documents; a database constraint requires a recognized area for every policy and `NULL` for every other source type. Policy uploads, listing, preview, rebuild, and delete remain admin-only; faculty never receive a policy-management or preview surface.

This extends the existing documents/reference-library lifecycle instead of creating a separate policy service. A generic reference type was rejected because criterion-targeted retrieval needs a stable policy-area filter and the UI must clearly distinguish policy assets from curriculum references.

### 2. Policies use a dedicated local Chroma collection

Policy documents are chunked at clause/numbered-paragraph boundaries with a smaller target (about 100–250 tokens) and embedded in `col_policy_all`. `DocumentChunk` persists policy area, section reference, and deterministic chunk ordering so rebuilds reproduce the same vector metadata. The same local embedding model is reused.

ITSO issues deterministic, criterion-specific policy queries: IP/ownership for ITSO-03, privacy/confidentiality for ITSO-04, and faculty/student rights for ITSO-05. Each query retrieves a small bounded set (up to five) from the matching policy area, with an optional `general_itso` fallback. Retrieval first derives a SQL allowlist of healthy active policy document IDs, filters Chroma by both area and that allowlist, and tie-sorts by stable chunk ID. A separate collection prevents policy clauses from competing with curriculum retrieval and permits precise metadata filtering.

### 3. Evidence is prepared before ITSO dispatch and fails open

Policy retrieval occurs while Supervisor builds an immutable, attempt-scoped `ItsoEvidenceSnapshot` before parallel agent dispatch. The snapshot holds bounded prompt-time policy clauses. A separate `ItsoEvidenceProvenance` is derived from that snapshot and contains only hashes, labels, statuses, counts, delivery/trim indicators, and configuration/version metadata.

Failures in policy retrieval or missing policies do not fail the evaluation. The agent receives an explicit evidence-unavailable state and must request human review where the criterion cannot be grounded. Policy evidence has a distinct prompt section and is omitted from provenance. If prompt budgeting drops or trims it, provenance records that it did not fully reach the model. Code-owned guardrail instructions keep all outcomes advisory and non-punitive.

### 4. Provenance is bounded and raw content remains excluded

Persist only allowlisted, recursively size-capped outcome data: opaque policy labels/chunk hashes, policy availability/outcome states, served model, and existing repair/trim indicators. Never persist raw SLM text, prompt text, policy clauses, policy document IDs, citation excerpts, credentials, or response payloads. Sanitize at both the successful and failed-result persistence boundaries.

## Risks / Trade-offs

- **[No authoritative policies uploaded]** → Return explicit per-area unavailable evidence and require human review; do not infer policy compliance.
- **[Policy retrieval returns irrelevant clauses]** → Use a separate collection, policy-area metadata filter, clause-level chunks, and criterion-specific fixed queries.
- **[Policy evidence biases an LLM conclusion]** → Prompt wording defines evidence as advisory and requires a human-review flag for inconclusive or conflicting evidence.
- **[Policy source is deleted after use]** → Historical results retain only hash/label audit evidence; deleted policy source material cannot be re-inspected. A future policy-versioning/archival change may strengthen this behavior.
- **[External LLM would receive policy clauses]** → Policy prompt injection is disabled unless the configured LLM backend is institutionally approved and local/self-hosted. Crossref never receives policy or SLM text.

## Migration Plan

1. Apply the schema migration for policy classification and chunk metadata.
2. Deploy config defaults with policy-to-LLM delivery disabled.
3. Upload authoritative policy PDFs through the new admin-only policy workflow and confirm policy health/embeddings.
4. Enable policy-to-LLM delivery only after institutional approval of a local/self-hosted LLM backend.
5. Roll back by disabling policy-to-LLM delivery; existing results remain readable. Policy documents remain local without changing historical scores.

## Open Questions

- Which authoritative SCC/LSPU documents will be uploaded first for IP ownership, RA 10173/privacy, and faculty/student rights?
- DOI-only Crossref verification is deferred to a dedicated future change.
