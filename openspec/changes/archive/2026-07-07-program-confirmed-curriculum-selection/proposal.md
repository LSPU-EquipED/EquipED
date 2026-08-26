## Why

Faculty evaluation currently starts automatically when the SLM evaluation page opens, submitting only the SLM document ID. That skips the new Reference Library capability and can run evaluations without the correct CHED curriculum grounding. Since CHED curriculum references are program-based and General Education/minor subjects can appear across multiple programs, course code alone must not determine the curriculum.

The system needs a short setup step before evaluation: show detected SLM metadata, require or prefill the academic program, suggest the matching CHED curriculum for that program, and submit the evaluation with the selected `curriculum_id`.

## What Changes

- Add a program-confirmed curriculum selection step before evaluation submission
- Stop auto-submitting evaluations before curriculum confirmation
- Suggest CHED curriculum references by confirmed program, not by course code
- Treat course code, Sem/AY, and lesson title as context only
- Keep syllabus out of this flow; `syllabus_id` remains optional/null
- Require usable curriculum references to be processed and embedding-ready
- Require curriculum references to have a program in the admin upload/library flow
- Preserve RAG: selection chooses the curriculum document; Chroma retrieval still retrieves relevant chunks during evaluation

## Capabilities

### New Capabilities
- `program-confirmed-curriculum-selection`: Faculty confirms the program and selected curriculum before starting evaluation

### Modified Capabilities
- `evaluations`: Evaluation submission remains owner-scoped for SLMs but should include confirmed curriculum references when available
- `reference-library`: Curriculum references need program metadata to support reliable suggestion

## Impact

- **Frontend**: evaluation page gets a setup step before the existing evaluation workspace; submit payload includes `curriculum_id`
- **Backend**: documents module exposes curriculum suggestions for an SLM/program; evaluation validation continues to enforce processed/embedded references
- **Admin UI**: curriculum upload/reference management must surface or require program metadata for curriculum references
- **Data model**: no schema change expected if existing `program` field is reused
- **RAG**: unchanged; the selected curriculum narrows which reference document is used for retrieval

## Out of Scope

- Syllabus picker
- Course-code to program catalog
- Semantic/vector matching for choosing the curriculum document
- Fuzzy matching
- Auto-submit without faculty confirmation
- ITSO citation/reference verification
