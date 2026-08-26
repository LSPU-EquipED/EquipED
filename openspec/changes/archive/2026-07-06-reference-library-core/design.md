## Context

EquipED is moving toward LSPU-hosted, local-first deployment: the backend, local database, uploaded PDFs, and ChromaDB vector store will live on an institution-controlled server. Reference documents already flow through upload, chunking, embedding, and retrieval, but there is no managed admin library for syllabus/curriculum files. This creates two immediate problems: admins cannot inspect or clean up reference assets, and faculty-owned evaluations cannot safely rely on admin-uploaded references until shared-reference access is explicit.

Rubrics are intentionally excluded from this library. They have separate prompt/rubric management concerns and should not be mixed with syllabus/curriculum reference management.

## Goals / Non-Goals

**Goals:**
- Provide an admin Reference Library page for syllabus and curriculum documents
- Show local storage health: PDF file availability, DB chunk count, Chroma vector availability, processing status
- Allow PDF preview from local uploads
- Allow admin-only delete that removes the document, chunks, Chroma vectors, and local file
- Allow admin-only embedding rebuild when chunks exist but local Chroma vectors are missing
- Formalize shared reference access: authenticated users may read/use syllabus/curriculum references; SLMs remain owner-only
- Keep the design local-first and LSPU-server friendly

**Non-Goals:**
- Faculty reference picker or auto-suggest matching
- Metadata editing UI
- Reference versioning or changelog
- Bulk upload
- Full-text search over reference content
- ITSO citation/reference verification
- Remote ChromaDB, cloud object storage, or cross-machine sync

## Decisions

### 1. Extend `documents/` instead of adding a new backend module

Reference documents are still `Document` rows with chunks, local files, and Chroma vectors. The documents module already owns upload, storage, ingestion, and document access rules, so reference library operations should extend that module rather than creating a separate `references` module that would duplicate or cross-own document lifecycle logic.

### 2. References are shared for read/use, SLMs remain owner-only

Access rules:

| Document type | Read/detail/file access | Evaluation use | Management/delete |
| --- | --- | --- | --- |
| `slm` | Owner only | Owner only | Owner only/admin later if needed |
| `syllabus`, `curriculum` | Authenticated users | Authenticated users may attach to own SLM evaluations | Admin only |
| `rubric_*` | Not part of Reference Library | Existing rubric/evaluation behavior | Existing admin-only rubric flow |

This fixes the current mismatch where references are uploaded by admins but evaluation validation can require the reference to be owned by the faculty user.

Access checks should use a single helper in the documents service layer, equivalent to:

```python
def _is_document_accessible(document, current_user_id: UUID) -> bool:
    if document.source_type in {"syllabus", "curriculum"}:
        return True
    return document.uploaded_by == current_user_id
```

The existing document list/detail behavior should also follow this rule: authenticated users may see shared syllabus/curriculum references when filtering/listing documents, while SLMs remain owner-scoped.

### 3. Local health is computed, not stored

Health indicators should be computed at request time:

- `file_exists`: whether the local PDF path exists
- `chunk_count`: number of `DocumentChunk` rows
- `chroma_vector_count` or `chroma_available`: whether local Chroma has vectors for the document
- `processing_status`: existing DB status
- `embedding_status`: derived from processing status, chunk count, and Chroma availability

No new health columns are needed. Local folders can be reset independently of the DB, so persisted health would drift.

### 4. Delete must clean all local assets

Reference delete must be admin-only and cleanup best-effort but explicit:

1. Delete Chroma vectors by `document_id` in the collection mapped by `source_type`
2. Delete `DocumentChunk` rows
3. Delete the `Document` row
4. Delete the local PDF file if it exists

If Chroma vectors or the file are already missing, deletion should still complete and report the cleanup outcome.

Delete must first check whether any `EvaluationJob` references the document through `syllabus_id` or `curriculum_id`. If referenced, the endpoint should reject deletion with `409 Conflict` and a clear message rather than nullifying history or causing an FK integrity error.

### 5. Rebuild embeddings from stored chunks

If chunks exist but Chroma vectors are missing, admins should be able to rebuild embeddings without re-uploading the PDF. The rebuild action should only support embedded reference types (`syllabus`, `curriculum`) and should reuse the existing embedding service path for stored chunks.

### 6. Preview streams local PDFs through authenticated endpoint

Use an authenticated file endpoint that streams the stored PDF with `Content-Type: application/pdf` and inline content disposition. The frontend can use an iframe or browser PDF view. SLM previews remain owner-only; reference previews are available to authenticated users, though Part 2 only builds the admin UI.

### 7. API response shapes are purpose-specific

The reference library list should not reuse the full document detail response because it would include chunks unnecessarily. It should return lightweight items with document metadata plus computed health:

- `document_id`, `title`, `source_type`, `program`, `course_code`, `academic_year`, `course_title`, `lesson_title`, `page_count`, `uploaded_at`, `uploaded_by`, `processing_status`
- `file_exists`, `chunk_count`, `chroma_available`, `embedding_ready`

Delete should return `{ document_id, deleted, warnings }`. Rebuild should return `{ document_id, rebuilt, chunk_count, warnings }` or equivalent.

## Risks / Trade-offs

- **[Chroma count can be expensive or API-dependent]** → Prefer a lightweight metadata-filtered count where possible; otherwise expose boolean availability from a limited query.
- **[Best-effort cleanup can partially fail]** → Return/report cleanup details and log failures, but do not leave the UI pretending cleanup was complete if a step failed.
- **[Shared references broaden read access]** → Limit shared access to syllabus/curriculum only; keep SLMs owner-only and rubrics out of this library.
- **[No metadata editing yet]** → Detected metadata may be imperfect. This is acceptable because Part 2 focuses on lifecycle management; editing is a later reference-library enhancement.
- **[Local storage drift]** → Health checks and rebuild are included specifically because local DB/uploads/Chroma can drift during development or server operations.
