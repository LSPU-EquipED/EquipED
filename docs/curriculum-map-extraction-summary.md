# Curriculum ingestion: multi-program CMO support

## Problem

`uploads/curriculum_dataset/CMO_CS-IT.pdf` is CHED CMO No. 25 s. 2015 —
a single 57-page PDF that covers **three** programs at once (BSCS, BSIS,
BSIT). LSPU SCC only offers CS and IT, not IS.

The existing extractor (`extract_curriculum_courses`) was built and
validated against a *different* CMO shape: one course per page, with a
"COURSE NAME" header and a two-column label/value layout. Run against
this document it correctly recognizes the layout doesn't match and
returns 0 records — verified before making any changes.

## Before

```
ingestion.py: ingest_document(source_type="curriculum")
  -> _ingest_curriculum_courses()
       -> extract_curriculum_courses(file_path)   # single-course-per-page CMOs only
       -> [] on this document (layout not recognized)
  -> falls back to generic page-by-page chunking
       -> every page becomes a chunk, undifferentiated by program
       -> BSCS, BSIS, and BSIT content all ingested together
       -> no way to exclude Information Systems content
```

Net effect: the document would still ingest (nothing crashes), but as
generic front-matter-to-back-matter page chunks with no program
awareness — IS content (which the university doesn't teach) would sit in
Chroma right alongside CS/IT content, degrading Coordinator's
curriculum-alignment retrieval for every course.

## What the document actually looks like

Confirmed by OCR-ing the real file: after the front matter, this CMO
organizes course learning-outcome tables per program, each behind an
explicit section header:

| Page | Header found |
|---|---|
| 21 | "Curriculum Map for the Bachelor of Science in **Computer Science**" |
| 25 | "Curriculum Map for the Bachelor of Science in **Information Systems**" |
| 28 | "Curriculum Map for the Bachelor of Science in **Information Technology**" |
| 34 | "Section 11 Sample Means of Curriculum Delivery" (end of course tables) |

Within a program's table, OCR of the multi-column row layout scrambles
which learning-outcome text belongs to which exact course row (a known,
accepted limitation — same class of problem the module's docstring
already flags for its other extractor). Section headers, by contrast,
OCR cleanly and appear as clean anchor lines, so they're a reliable
signal even when row-level detail isn't.

## After

Added `extract_curriculum_map_courses()` to
`server/modules/documents/curriculum_extraction.py` as a second, distinct
extraction strategy, and wired it into `ingestion.py` as a **second-pass
fallback** — tried only if the existing single-course-per-page extractor
returns nothing:

```
ingestion.py: ingest_document(source_type="curriculum")
  -> _ingest_curriculum_courses()
       -> extract_curriculum_courses(file_path)          # unchanged, tried first
       -> if empty: extract_curriculum_map_courses(file_path)   # NEW
            - scans each page's text for a
              "Curriculum Map for the Bachelor of Science in <Program>"
              header; tracks which program's section the page is in
            - keeps a page only while inside a section whose program
              name matches an allow-list (default: computer science,
              information technology)
            - stops including pages once "Section 11 / Sample Means of
              Curriculum Delivery" is seen (end of the course tables)
            - one chunk per included page (not per course — row-level
              OCR is too scrambled to split reliably), title = the
              course codes detected on that page, description = the
              page's full text
  -> falls back to generic page chunking only if BOTH extractors return []
```

Run against the real file:

- `extract_curriculum_courses` → 0 records (as before — correctly
  recognizes this isn't its layout).
- `extract_curriculum_map_courses` → 11 records: pages 21-24 (Computer
  Science) and 28-34 (Information Technology). Pages 25-27 (Information
  Systems) are excluded entirely, never reach Chroma.

## Why page-level chunks, not per-course

The single-course-per-page extractor can afford one record per course
because each course gets a dedicated page with a clean label/value
column split. This CMO's "curriculum map" tables pack many courses'
learning outcomes into one continuous, multi-column table per program —
OCR reliably finds the section header but not which exact row a given
learning-outcome sentence belongs to (rows visibly shift by about one
course down in the raw OCR output). Rather than fabricate a false sense
of per-course precision, this extracts one chunk per page: still
correctly scoped to CS/IT only, and every course's real content is
present and retrievable via Chroma's semantic search — just chunked at
page granularity instead of course granularity for this layout.

## Program filtering is reusable, not hardcoded to this file

`extract_curriculum_map_courses(file_path, included_programs=...)` takes
the allow-list as a parameter (default `("computer science",
"information technology")`). Any future CMO using this same
multi-program "Curriculum Map" section-header layout is handled
automatically without code changes — only a document that actually
contains that exact header pattern triggers this path at all, so it's
safe as an unconditional second-pass fallback for every curriculum
upload.

## Tests

`server/tests/documents/test_curriculum_map_extraction.py` (new, 5 tests,
fast — mocks `fitz` so no real OCR runs):
- default allow-list includes only CS and IT section pages
- the "Section 11" end marker stops inclusion even without a new header
- a custom `included_programs` narrows selection (verified by
  requesting Information Systems specifically)
- a document with no matching header returns `[]` (confirms this is
  safe to always attempt as a fallback)
- detected course codes make it into the chunk title

Full `server/tests/documents` suite run: 12 pre-existing failures/7
errors, all confirmed present on the base branch too (Windows
tempfile-locking and hardcoded `/tmp` path issues, unrelated to this
change) — nothing regressed by this change.
