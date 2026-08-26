## Context

The document preprocessing pipeline in `server/modules/documents/service.py` currently extracts text, chunks, structured summaries, outlines, and key facts from uploaded PDFs. However, metadata like `program`, `academic_year`, `course_code`, and `lesson_title` are either manually entered or not captured at all.

The Phase 2 reference picker needs reliable `program` metadata on both SLMs and reference documents to auto-suggest matching syllabi/curricula during evaluation submission. Manual entry is unreliable — admins skip fields, make typos, or don't know the exact program code.

The existing preprocessing pipeline runs as a FastAPI BackgroundTask after upload. It already has access to the full extracted text. Adding a regex-based detection step is a natural fit with zero LLM cost and negligible runtime overhead.

## Goals / Non-Goals

**Goals:**
- Auto-detect `program` from document text using regex pattern matching — not forced if absent
- Auto-detect `academic_year` from cover page patterns
- Auto-detect `course_code` from title page patterns
- Auto-detect `lesson_title` from cover page labels (e.g., `Lesson Title:`)
- Populate detected metadata automatically during preprocessing
- Add `academic_year` and `course_code` columns to the Document model
- Keep detection non-blocking — failures leave fields null
- Support future reference picker by providing reliable program metadata

**Non-Goals:**
- LLM-based metadata extraction (deferred — too costly, even for localized models)
- Metadata editing UI (part of the reference library change, not this one)
- Auto-detection of author, department, or description (too unreliable with regex)
- Validation of detected values against a canonical list of programs (future enhancement)
- Re-processing existing documents (only applies to new uploads)
- Detection of week duration, module number, or semester (not currently needed)

## Decisions

### 1. Regex-only detection (no LLM)

**Decision:** Use Python `re` module for pattern matching. No LLM calls.

**Rationale:** The user explicitly requested regex-only to avoid LLM costs and preprocessing complexity. Regex is deterministic, fast (<100ms), and has zero token cost. Even with future localized models, adding an LLM call to preprocessing is unnecessary overhead for fields that follow recognizable patterns.

**Alternatives considered:**
- LLM extraction: more flexible but costly and slow (~5-10s per document)
- Hybrid (regex + LLM fallback): adds complexity for marginal gain

### 2. Scan first 2-3 pages only

**Decision:** Run regex patterns against text from the first 2-3 pages (cover page + title page) only.

**Rationale:** Program codes, academic years, and course codes appear on cover/title pages. Scanning the full document increases false positives (e.g., a course code mentioned in a reference section on page 15).

**Implementation:** Use the first ~6000 characters of extracted text, or the first 3 pages worth of text, whichever is smaller.

### 3. Known program list + pattern matching

**Decision:** Maintain a curated list of LSPU SCC program codes and match against them.

**Patterns:**
```
Program:      \b(BSIT|BSED|BSCS|BSBA|BSCE|BSEE|BSME|BSN|AB[A-Z]+|BSECE|BSCpE)\b
Academic year: \b(20\d{2})\s*[-–]\s*(20\d{2})\b  or  \bAY\s*20\d{2}\b
Course code:  \b([A-Z]{2,4})\s*(\d{3})\b
Lesson title: Lesson Title:\s*(.+)
```

**Rationale:** LSPU SCC has a finite set of programs. Matching against a known list reduces false positives significantly vs matching any 4-letter acronym.

**Alternatives considered:**
- Match any `[A-Z]{2,4}` pattern: too many false positives (e.g., "PDF", "URL")
- LLM extraction: overkill for a known finite list

### 4. New module: `server/modules/documents/metadata.py`

**Decision:** Create a dedicated `metadata.py` file in the documents module for detection logic.

**Rationale:** Keeps detection logic separate from the main service file (which is already 500+ lines). The function signature:

```python
def detect_metadata(text: str) -> dict[str, str | None]:
    """Extract program, academic_year, course_code, lesson_title from document text."""
    return {
        "program": _detect_program(text),
        "academic_year": _detect_academic_year(text),
        "course_code": _detect_course_code(text),
        "lesson_title": _detect_lesson_title(text),
    }
```

### 5. Nullable columns, no migration of existing data

**Decision:** Add `academic_year` and `course_code` as nullable columns. Existing documents keep null values. Only new uploads get auto-detected metadata.

**Rationale:** Re-processing existing documents would require re-running preprocessing, which is expensive and risky. Null values are handled gracefully — the reference picker falls back to showing all references when program is null.

### 6. Non-blocking detection

**Decision:** Detection failures do not affect preprocessing status. If regex finds nothing, fields stay null and the document still processes normally.

**Rationale:** Detection is a best-effort enhancement, not a critical step. Documents without clear program markers (e.g., rubric PDFs) should still upload and process fine.

## Risks / Trade-offs

- **[False positives]** → Regex may match patterns in body text, not just cover pages. Mitigation: scan first 2-3 pages only, use known program list.
- **[Missing programs]** → LSPU SCC may add new programs not in the curated list. Mitigation: make the list configurable via settings or a constant that's easy to update.
- **[Varied formats]** → Some documents may use non-standard formats (e.g., "Bachelor of Science in Information Technology" instead of "BSIT"). Mitigation: accept this limitation for Phase 2; the admin can edit metadata later.
- **[Course code ambiguity]** → `[A-Z]{2,4}\s*\d{3}` may match non-course-code patterns. Mitigation: only apply to first 2-3 pages where course codes are expected.
- **[No re-processing]** → Existing documents won't have detected metadata. Mitigation: acceptable for Phase 2; future batch re-processing script can be added if needed.
