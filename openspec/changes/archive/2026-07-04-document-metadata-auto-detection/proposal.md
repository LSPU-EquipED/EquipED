## Why

Reference documents (syllabi, curricula, rubrics) and SLMs currently rely on manual metadata entry — the admin types a title and optionally a program. This is error-prone, inconsistent, and blocks the Phase 2 reference picker, which needs reliable `program` metadata to auto-suggest matching references during evaluation submission. Auto-detecting metadata from document content removes friction and makes the reference matching pipeline viable.

## What Changes

- Add regex-based metadata extraction to the document preprocessing pipeline
- Auto-detect `program` (e.g., BSIT, BSED, BSCS) from the first 2-3 pages of extracted text — not forced if absent
- Auto-detect `academic_year` (e.g., 2025-2026) from cover page patterns
- Auto-detect `course_code` (e.g., CCS 101, CMSC 313) from title page patterns
- Auto-detect `lesson_title` (e.g., HUMAN INPUT-OUTPUT CHANNELS) from cover page labels like `Lesson Title:`
- Add nullable columns `academic_year` and `course_code` to the `Document` model
- Populate `program` automatically during preprocessing instead of relying on manual entry
- Populate `lesson_title` automatically only if not manually provided
- Detected metadata is saved automatically and editable later (non-blocking)
- If detection fails, fields remain null — no blocking or errors
- No LLM calls — pure regex pattern matching, adds <100ms to preprocessing

## Capabilities

### New Capabilities
- `document-metadata-detection`: Regex-based extraction of program, academic year, course code, and lesson title from document text during preprocessing

### Modified Capabilities
- `custom-semantic-document-chunking`: Preprocessing pipeline now includes a metadata detection step after text extraction

## Impact

- **Backend**: `server/modules/documents/service.py` (preprocessing pipeline), `server/modules/documents/models.py` (new columns), new `server/modules/documents/metadata.py` (detection logic), Alembic migration for new columns
- **Frontend**: Upload form can show detected metadata after preprocessing completes
- **No new dependencies**: Uses only Python `re` module
- **No API changes**: Metadata is populated server-side during existing preprocessing
- **No LLM cost**: Pure regex, no token consumption
