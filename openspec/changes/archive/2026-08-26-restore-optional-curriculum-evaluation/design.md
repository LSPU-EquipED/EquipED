## Context

The current product intentionally supports only BSCS and BSInfoTech, but PR #85 retired curriculum ingestion and forced every new faculty evaluation into partial mode. The data model and downstream full-evaluation runtime remain intact: documents and jobs still carry curriculum/program fields; Supervisor can schedule Coordinator; supervision can load authoritative curriculum chunks; Coordinator can compute curriculum-grounded A-05; and synthesis can produce a full matrix.

Active blockers are admission and reachability gates: curriculum upload/reference access is rejected, the suggestion endpoint is an empty deprecated stub, evaluation admission rejects curriculum identity, and the client exposes only partial acknowledgement. The specialized historical curriculum extractor was later deleted after becoming dead code. Current ingestion has a deterministic page-bounded semantic chunker and fail-closed OCR suitable for authoritative text loading.

## Goals / Non-Goals

**Goals:**

- Restore admin-only curriculum ingestion and local indexing for BSCS and BSInfoTech.
- Restore program-matched curriculum suggestions and an accessible faculty choice between full and explicit partial evaluation.
- Reuse the dormant Coordinator/full-synthesis path without altering agent architecture.
- Preserve ownership masking, local data residency, fail-closed OCR, lifecycle honesty, and historical results.

**Non-Goals:**

- Supporting programs beyond BSCS and BSInfoTech; `BSIT` remains only a read alias for `BSInfoTech`.
- Restoring rubric PDF upload, the brittle historical column-split OCR implementation, or curriculum selection in Model Validation.
- Automatically downgrading a requested full evaluation when curriculum or Coordinator becomes unavailable.
- Introducing new tables, columns, background systems, external storage, or LLM behavior.

## Decisions

### Reuse the existing reference ingestion pipeline

Curriculum becomes an active reference source again and uses the current fail-closed extraction, deterministic page-bounded chunking, SQL chunk persistence, and local Chroma reference collection. This avoids restoring a layout-specific numpy/OCR implementation before authoritative curriculum formats are collected.

For a PDF that contains recognizable multi-program curriculum-map section headers, ingestion applies deterministic section-aware text trimming before chunking, including when two section boundaries share one page: retain only text within the selected canonical program section and stop at the next program header or a known map-end marker. Recognized program headings include Computer Science, Information Technology, and other `Curriculum Map for the Bachelor of Science in ...` forms; recognized end markers include `Section 11` and `Sample Means of Curriculum Delivery`. If no map headers and no other-program indicators exist, treat the admin-tagged document as single-program and retain all pages. If another-program indicator exists but boundaries cannot be resolved, or the selected section is absent, fail ingestion rather than mix programs.

Alternative rejected: store all pages and rely on `Document.program`. Coordinator concatenates every curriculum chunk and cannot safely isolate unrelated program sections.

### Keep two explicit launch intents

Both modes require confirmed canonical program context. Write requests accept only `BSCS` or `BSInfoTech`; `BSIT` is accepted only while reading or filtering legacy data:

- Full: `curriculum_id` present and `partial_without_curriculum=false`.
- Partial: no `curriculum_id` and `partial_without_curriculum=true`, with explicit acknowledgement in the client.

Both Boolean values are explicit and conflicting or omitted combinations are rejected. The partial acknowledgement is a client gate represented by `partial_without_curriculum=true`; no separate persisted acknowledgement column is added. A full submission requires a curriculum that passes the documents-owned readiness boundary and matches `confirmed_program`. SLM lookup, source-type validation, and ownership masking occur before program or curriculum validation.

Alternative rejected: infer intent from curriculum presence. Explicit intent keeps API behavior auditable and preserves historical semantics.

### Reuse the dormant full runtime unchanged

Full jobs use the existing Supervisor default agent set, authoritative curriculum text loader, Coordinator dispatch, SME/Coordinator reconciliation, and full synthesis weights. Partial jobs continue excluding Coordinator before dispatch and use renormalized weights.

A full job whose curriculum becomes unavailable or whose Coordinator fails must synthesize available outputs and terminate both job and monitoring matrix as `FAILED`; it must never become `COMPLETED_PARTIAL`. A successful intentional partial job uses matrix `COMPLETED_PARTIAL`; a failed partial job uses matrix `FAILED`. Full or partial intent remains on the associated job/result and is not a monitoring-matrix column.

### Centralize curriculum readiness in documents

One documents-owned readiness service is used by suggestions and evaluation admission. It requires current admin provenance, `source_type=curriculum`, canonical matching program, `PROCESSED`, non-empty persisted chunks, and live vector availability in the local curriculum collection. The SQL `chroma_stored` flag alone is insufficient. Legacy faculty-uploaded curriculum rows and stale-vector rows are unavailable.

### Restore suggestions as an ownership-scoped read model

The curriculum suggestion endpoint first validates that the target exists, is an SLM, and belongs to the caller, using the same masked response for missing, foreign, and non-SLM IDs. It then validates the explicitly confirmed program and returns matching curriculum documents with documents-owned readiness metadata. Faculty must explicitly select a ready curriculum; no automatic preferred curriculum is chosen. Unready matches may be shown for truthful recovery guidance but cannot be submitted. Generic faculty document listing continues to exclude curriculum discovery; faculty discover curricula only through this scoped endpoint, though selected shared PDFs may be previewed.

Evaluation submission logic and mutations live in `features/evaluation`; the evaluation feature SHALL NOT import the upload feature. Upload retains only its upload-completion navigation responsibility.

### Ordinary per-document reference deletion

Ordinary per-document curriculum deletion blocks when any evaluation, terminal or non-terminal, references that curriculum. It must fail observably if vector cleanup fails and must not delete the SQL row.

## Risks / Trade-offs

- **Multi-program PDF contamination** → Trim extracted text at section boundaries, including same-page transitions, and fail when other-program indicators cannot be resolved safely.
- **Wide `REFERENCE_SOURCE_TYPES` blast radius** → Add endpoint/access/delete/rebuild tests for curriculum and keep syllabus-only selectors explicitly source-filtered.
- **Full jobs silently degrading** → Preserve existing required-agent validation and add terminal-state integration coverage.
- **UI ambiguity between full and partial** → Use a radio-group curriculum selector and show partial acknowledgement only when the partial option is selected.
- **Dirty working tree from prior completed work** → Maintain disjoint implementation lanes and validate the final integrated diff without committing automatically.

## Migration Plan

1. Land spec and code changes; no database migration is required.
2. Deploy server before exposing the client selection controls so curriculum submissions are accepted.
3. Admin uploads and verifies BSCS/BSInfoTech curriculum references.
4. Smoke-test one partial and one full evaluation; confirm Coordinator attribution and terminal matrix status.
5. Roll back by hiding the client options and restoring admission rejection; existing uploaded curricula can remain inert.

## Open Questions

None. The user selected optional full flow with explicit partial fallback.
