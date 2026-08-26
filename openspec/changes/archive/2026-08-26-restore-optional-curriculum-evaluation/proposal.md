## Why

Curriculum ingestion and curriculum-grounded evaluation were retired even though the product only needed to restrict active program support to BSCS and BSInfoTech. This change restores the existing dormant full-evaluation path while preserving explicit partial evaluation when no curriculum is selected.

## What Changes

- Allow administrators to upload, process, index, list, rebuild, and delete curriculum references for BSCS and BSInfoTech only; `BSIT` remains a read alias for canonical `BSInfoTech`.
- Restore program-matched curriculum suggestions in the faculty evaluation setup.
- Let faculty select a processed curriculum for a full evaluation or explicitly acknowledge a partial evaluation without curriculum.
- Schedule Coordinator only for full-intent evaluations and preserve the existing honest failure behavior when authoritative curriculum becomes unavailable.
- Keep SLM ownership masking, admin-only curriculum management, fail-closed OCR, local reference embedding, and historical partial-job semantics.
- Do not restore unsupported programs, rubric PDF upload, automatic full-to-partial downgrade, or curriculum selection in Model Validation.

## Capabilities

### New Capabilities

- `curriculum-reference-extraction`: Admin-only curriculum PDF ingestion, program validation, fail-closed extraction, local reference indexing, and readiness for selection.

### Modified Capabilities

- `upload-rbac`: Permit curriculum upload for administrators while faculty remain restricted to SLM upload.
- `reference-library`: Restore curriculum as an active, shared reference lifecycle alongside syllabus references.
- `program-confirmed-curriculum-selection`: Offer program-matched processed curricula and submit selected curriculum identity for full evaluation.
- `partial-evaluation-without-curriculum`: Change partial evaluation from the only launch path to an explicit acknowledged fallback.
- `evaluations`: Accept full intent with curriculum, require Coordinator for that intent, and preserve honest terminal-state behavior.
- `monitoring-matrix`: Keep matrix terminal status aligned with intentional partial, successful full, and failed full job intent.
- `custom-semantic-document-chunking`: Apply the active reference chunking/indexing contract to curriculum documents.

## Impact

- Server: documents ingestion/access/reference lifecycle, curriculum suggestion endpoint, evaluation admission validation, and existing Coordinator full-flow tests.
- Client: admin reference ingestion, shared curriculum suggestion API/types, faculty evaluation setup state and accessible selection UI.
- Contracts: seven modified capabilities and one restored curriculum extraction capability.
- Storage: no database migration; existing document, evaluation, curriculum pointer, program, chunk, and embedding structures are reused.
- Runtime: no Coordinator, Supervisor, orchestration, synthesis, or model-routing rewrite.
