## Why

ITSO currently evaluates IP, references, ownership, confidentiality, and rights from SLM text plus local advisory prechecks alone. It has no authoritative policy clauses for the ownership, privacy, or rights criteria.

This change adds bounded, auditable local policy evidence while preserving the system's local-data-residency and human-review constraints.

## What Changes

- Add an admin-managed local policy evidence library for authoritative IP, privacy, and faculty/student-rights documents.
- Ingest policy PDFs into a dedicated local Chroma collection with clause-oriented chunks and policy metadata.
- Retrieve targeted local policy clauses for ITSO-03 (ownership), ITSO-04 (confidentiality), and ITSO-05 (rights), with honest unavailable-evidence handling when a policy is absent or unhealthy.
- Record bounded policy-retrieval outcomes in ITSO provenance without retaining raw SLM/prompt or policy-clause text.
- Update the ITSO prompt contract so policy retrieval remains advisory: unavailable policy evidence is never treated as proof of misconduct or legal noncompliance.

## Capabilities

### New Capabilities
- `itso-evidence-tools`: Local policy-clause retrieval that provides bounded, advisory evidence to ITSO evaluation.

### Modified Capabilities
- `reference-library`: Expand the admin-managed local library to include policy documents and their lifecycle/health actions without exposing management actions to faculty.
- `itso-scoring-consistency`: Extend the frozen ITSO evidence snapshot and provenance contract with bounded policy-retrieval outcomes.
- `upload-rbac`: Restrict policy upload, listing, and use to the administrative ITSO evidence path rather than treating policies as faculty-visible shared references.
- `evaluations`: Permit policy documents as a distinct local embedding target while preserving the rule that SLMs are never embedded.

## Impact

- **Backend:** documents source-type/metadata validation, policy ingestion and collection routing, embeddings retrieval, ITSO precompute/prompt/provenance, and admin/reference APIs.
- **Frontend:** admin-only policy upload and policy-library management; no faculty policy-management surface.
- **Data:** policy documents, chunks, and vectors remain on LSPU-controlled storage; bounded provenance gains policy evidence outcome fields. A migration adds policy classification and persisted policy chunk metadata.
- **Governance:** Policy clauses may reach only an institutionally approved local/self-hosted LLM backend; they remain unavailable to external LLM endpoints. DOI-only Crossref verification is deferred to a separate future change.
