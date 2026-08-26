## 1. Database schema

- [x] 1.1 Add `academic_year` and `course_code` nullable columns to `Document` model in `server/modules/documents/models.py`
- [x] 1.2 Create Alembic migration to add the two new columns
- [x] 1.3 Update `DocumentResponse` and `DocumentUploadResponse` schemas to include `academic_year` and `course_code`

## 2. Metadata detection logic

- [x] 2.1 Create `server/modules/documents/metadata.py` with `detect_metadata(text: str) -> dict[str, str | None]`
- [x] 2.2 Implement `_detect_program(text)` — regex match against known LSPU SCC program list
- [x] 2.3 Implement `_detect_academic_year(text)` — regex match for year range patterns
- [x] 2.4 Implement `_detect_course_code(text)` — regex match for course code patterns
- [x] 2.5 Implement `_detect_lesson_title(text)` — regex match for `Lesson Title:` label
- [x] 2.6 Update `detect_metadata()` return dict to include `lesson_title`
- [x] 2.7 Limit detection to first ~6000 characters of text (first 2-3 pages)

## 3. Preprocessing pipeline integration

- [x] 3.1 Call `detect_metadata()` in the preprocessing pipeline after text extraction, before embedding
- [x] 3.2 Persist detected metadata to the `Document` record after preprocessing completes
- [x] 3.3 Do NOT overwrite `program` if it was manually set during upload
- [x] 3.4 Do NOT overwrite `lesson_title` if it was manually set during upload
- [x] 3.5 Wrap detection in try/except — log warning on failure, continue preprocessing

## 4. Tests

- [x] 4.1 Test `_detect_program()` with known programs (BSIT, BSED, BSCS)
- [x] 4.2 Test `_detect_program()` rejects non-program acronyms (PDF, URL)
- [x] 4.3 Test `_detect_academic_year()` with standard formats (2025-2026, AY 2025)
- [x] 4.4 Test `_detect_course_code()` with standard formats (CCS 101, IT 201)
- [x] 4.5 Test `detect_metadata()` returns all nulls when no patterns match
- [x] 4.6 Test detection only scans first 2-3 pages (pattern on page 15 is ignored)
- [x] 4.7 Test detection does not block preprocessing on exception
- [x] 4.8 Test existing manual `program` is not overwritten by auto-detection
- [x] 4.9 Test `_detect_lesson_title()` with standard `Lesson Title:` labels
- [x] 4.10 Test `_detect_lesson_title()` returns None when no label present
- [x] 4.11 Test SLM cover page integration — emits `course_code`, `academic_year`, `lesson_title`, no `program`
- [x] 4.12 Test manual `lesson_title` is preserved when provided
- [x] 4.13 Test `program` remains null when absent from content

## 5. Validation

- [x] 5.1 Run `server/tests/documents/` test suite — **all metadata tests pass**
- [x] 5.2 Run `server/tests/core/` test suite — **27 passed**
- [x] 5.3 Upload a test document and verify metadata is detected — **Validated via TestClient: real PDF with "CCS 101", "2025-2026", and "BSIT" patterns returns `academic_year="2025-2026"`, `course_code="CCS 101"` in both upload response and GET response. Manual `program` preserved.**
- [x] 5.4 Verify preprocessing still completes normally when no metadata is found — **Validated via TestClient: real PDF with no matching patterns returns `academic_year=None`, `course_code=None`, processing_status="PROCESSED", manual program preserved.**
- [x] 5.5 Run updated metadata tests — **lesson_title detection, SLM cover page, manual lesson_title preserved, program null when absent**
