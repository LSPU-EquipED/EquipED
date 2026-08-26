## Context

Part 1 added deterministic metadata detection for SLMs (`course_code`, `academic_year`, `lesson_title`, optional `program`). Part 2 added Reference Library Core for locally managed syllabus/curriculum documents. Part 3 connects these pieces to evaluation start: a faculty user should confirm the academic program and curriculum before the evaluation job is submitted.

CHED curriculum references are per program. Some SLMs, especially General Education/minor subjects such as Understanding the Self or Purposive Communication, do not identify the owning program. Therefore course code or subject title must never be treated as authoritative for curriculum selection.

## Goals / Non-Goals

**Goals:**
- Add an evaluation setup step before job submission
- Show detected SLM metadata for context
- Preselect program if detected, otherwise require faculty selection
- Suggest curriculum references using the confirmed program
- Submit evaluation with selected `curriculum_id`
- Keep syllabus unused in this flow
- Preserve RAG retrieval after selection

**Non-Goals:**
- Inferring program from GE/minor course codes
- Syllabus picker or syllabus auto-suggest
- Semantic search to choose a curriculum document
- Course-code to program catalog
- Metadata editing for references
- Automatic evaluation submission without human confirmation

## Decisions

### 1. Program is authoritative for curriculum selection

Curriculum selection SHALL be driven by confirmed program. Course code, Sem/AY, and lesson title are displayed for faculty context but do not determine the curriculum. This prevents false matches for GE/minor subjects shared across programs.

### 2. Curriculum suggestion is SQL/metadata-based, not RAG

The suggestion step selects the correct curriculum document. It should query reference metadata:

```txt
source_type = curriculum
normalize(program) = normalize(confirmed_program)
embedding_ready = true
```

RAG still happens later during evaluation: the selected curriculum document scopes the Chroma retrieval, and Chroma finds the relevant chunks/pages inside that document.

### 3. Evaluation setup interrupts auto-submit

The current evaluation page auto-submits when no prior evaluation exists. This change should insert a setup state:

```txt
Open SLM evaluation page
  -> load SLM metadata
  -> confirm/select program
  -> suggest curriculum
  -> faculty clicks Start Evaluation
  -> POST /evaluations/ with curriculum_id
```

Existing evaluation reuse should still work for completed/in-progress evaluations; the setup step is only needed before creating a fresh evaluation.

### 4. Curriculum references require program metadata

Admin-uploaded curriculum references must have a program value. Without it, the system cannot suggest the correct curriculum. This can be enforced in the admin upload UI and backend validation for `source_type=curriculum`.

### 5. No confident curriculum match blocks start

If no embedding-ready curriculum exists for the confirmed program, evaluation start should be blocked with a clear message and an admin-oriented recovery path: upload/rebuild the program's curriculum reference.

### 6. Syllabus remains optional/null

This flow does not select or require a syllabus. The evaluation request should send only `document_id` and `curriculum_id`; `syllabus_id` remains null/omitted.

## Suggested API

```txt
GET /documents/{document_id}/curriculum-suggestion?program=BSCS
```

Returns the SLM metadata plus curriculum candidates for the selected program:

```json
{
  "document_id": "...",
  "detected_program": null,
  "selected_program": "BSCS",
  "detected_course_code": "CMSC 313",
  "detected_academic_year": "2025-2026",
  "detected_lesson_title": "Human Input-Output Channels",
  "curriculum_suggestions": [
    {
      "document_id": "...",
      "title": "BSCS CHED Curriculum",
      "program": "BSCS",
      "embedding_ready": true,
      "match_reason": "selected_program"
    }
  ]
}
```

If multiple curriculum references match the program, the newest processed/embedding-ready item should be preselected and alternatives shown.

Program values should be normalized before comparison, using uppercase trimmed values. Curriculum uploads should persist normalized program codes where possible.

The endpoint should return both ready and unavailable matching curricula. Ready curricula are selectable. Unavailable curricula are shown as disabled with a recovery message so admins/faculty can see whether a matching curriculum exists but needs processing/rebuild.

## UX Sketch

```txt
Evaluation Setup
────────────────────────────────────────
Detected from SLM
Course Code: CMSC 313
Sem/AY: 2025-2026
Lesson: Human Input-Output Channels

Academic Program
[ BSCS ▼ ]

CHED Curriculum
✓ BSCS CHED Curriculum
Ready / Indexed

[Start Evaluation]
```

If no program was detected, the program selector is required before curriculum suggestion is shown. If no curriculum is found, show an explicit empty state and block start.

## Risks / Trade-offs

- **GE/minor ambiguity**: solved by requiring program confirmation instead of inferring from course code
- **Missing program on curriculum reference**: solved by requiring program on curriculum upload
- **Stale/unhealthy curriculum**: block start if no embedding-ready curriculum is available; admin can rebuild in Reference Library
- **Existing auto-submit expectations**: preserved for existing evaluations, changed only for fresh submission
- **No syllabus grounding**: intentional per current product direction; backend keeps optional syllabus support for future use
- **Case mismatch**: normalized uppercase program matching avoids false negatives between detected, selected, and stored program codes
