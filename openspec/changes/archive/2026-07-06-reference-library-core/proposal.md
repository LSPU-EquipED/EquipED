## Why

Reference documents are already uploaded and embedded, but administrators do not have a managed library for seeing, previewing, deleting, or repairing syllabus/curriculum references. This creates operational risk for the LSPU-hosted deployment: stale Chroma vectors can remain after replacement, local files can go missing, and faculty cannot reliably use admin-uploaded references until shared-reference access is formalized.

## What Changes

- Add an admin reference library for syllabus and curriculum documents only
- Let admins list reference documents with metadata, processing status, file health, chunk health, and Chroma health
- Add PDF preview for stored reference documents
- Add admin-only reference deletion that cleans up SQL rows, chunks, Chroma vectors, and local PDF files
- Add admin-only embedding rebuild for references when DB chunks exist but local Chroma vectors are missing
- Formalize shared reference access: SLMs remain owner-only, while syllabus/curriculum references are institution-shared for authenticated users
- Keep rubric PDFs out of this library because rubric management remains separate
- Keep storage local-first for the intended LSPU server deployment: local DB, local uploads, local ChromaDB

## Capabilities

### New Capabilities
- `reference-library`: Admin-managed syllabus/curriculum library with listing, health visibility, PDF preview, delete cleanup, and embedding rebuild

### Modified Capabilities
- `upload-rbac`: Clarify that admin-uploaded syllabus/curriculum references are institution-shared for read/use while management remains admin-only
- `evaluations`: Allow faculty-owned SLM evaluations to use shared syllabus/curriculum references without requiring reference ownership

## Impact

- **Backend**: extend `server/modules/documents/` with role-aware reference list/detail, file streaming, delete cleanup, health checks, and embedding rebuild; update evaluation reference validation ownership rules
- **Embeddings**: add Chroma delete-by-document and rebuild helpers for reference documents
- **Frontend**: add admin Reference Library page and integrate existing admin ingest flow with the library
- **Storage**: assumes LSPU-hosted local persistence for DB, `uploads/`, and `chroma_data/`; no cloud sync or remote vector store
- **Security**: SLMs remain owner-scoped; syllabus/curriculum references become shared read/use for authenticated users; delete/rebuild remains admin-only
- **Out of scope**: faculty reference picker, auto-suggest matching, metadata editing, versioning, bulk upload, full-text search, ITSO citation verification
