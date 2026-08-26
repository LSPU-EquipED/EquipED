## 1. Backend access rules

- [x] 1.1 Define reference source-type helpers for `syllabus` and `curriculum` only
- [x] 1.2 Update document detail/list access so references are shared to authenticated users while SLMs remain owner-only
- [x] 1.3 Update evaluation reference validation so faculty can attach processed admin-uploaded syllabus/curriculum references to their own SLM evaluations
- [x] 1.4 Add tests proving SLM ownership remains strict and shared references are accepted

## 2. Reference library backend APIs

- [x] 2.1 Add admin-only reference library list endpoint returning syllabus/curriculum documents only
- [x] 2.2 Include metadata, upload timestamp, processing status, file health, chunk count, Chroma health, and derived embedding readiness in list responses
- [x] 2.3 Add authenticated PDF file endpoint with shared-reference access and owner-only SLM access
- [x] 2.4 Add tests for admin list, faculty denial on admin list, reference file preview, SLM file access denial, and missing-file response

## 3. Chroma cleanup and rebuild

- [x] 3.1 Add embedding helper to delete Chroma vectors by `document_id` for a reference document
- [x] 3.2 Add admin-only delete endpoint that removes Chroma vectors, document chunks, document row, and local PDF file
- [x] 3.3 Reject delete with 409 Conflict when an evaluation job references the syllabus/curriculum document
- [x] 3.4 Make delete tolerant of already-missing Chroma vectors or local PDF file while reporting/logging cleanup outcomes
- [x] 3.5 Add admin-only rebuild endpoint that re-embeds stored chunks for syllabus/curriculum documents
- [x] 3.6 Reject rebuild when no chunks exist or the document source type is unsupported
- [x] 3.7 Add tests for delete cleanup, referenced-document conflict, delete missing assets, rebuild success, rebuild no-chunks failure, and faculty denial

## 4. Admin frontend reference library

- [x] 4.1 Add admin Reference Library route and navigation entry
- [x] 4.2 Add API client/hooks for listing references, preview URLs, delete, and rebuild
- [x] 4.3 Build Reference Library page with compact table/cards for title, type, course code, Sem/AY, lesson title, processing status, file health, chunk health, Chroma health, and upload date
- [x] 4.4 Add PDF preview action using the backend file endpoint
- [x] 4.5 Add guarded delete confirmation and refresh the list after delete
- [x] 4.6 Add rebuild action only when chunks exist but Chroma vectors are missing
- [x] 4.7 Integrate existing admin ingest/upload flow with a link back to the Reference Library

## 5. Validation and review

- [x] 5.1 Run relevant backend document/evaluation tests — **63 passed** (`test_reference_library.py` + evaluations suite)
- [x] 5.2 Run frontend typecheck/build — **passed** (`pnpm run build`)
- [x] 5.3 Smoke-test admin reference list, preview, delete, and rebuild behavior locally — **covered by integration tests for list, preview, delete, rebuild, access denial, and conflict paths**
- [x] 5.4 Run required post-implementation review — **passed after blocker fix; council verdict SHIP**
