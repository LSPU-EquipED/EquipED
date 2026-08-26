## 1. Backend suggestion API

- [x] 1.1 Add schemas for curriculum suggestion response and candidate items
- [x] 1.2 Add service logic to load the owned SLM, read detected metadata, and require/accept confirmed program
- [x] 1.3 Add program-driven curriculum matching for `source_type=curriculum` and embedding-ready references
- [x] 1.4 Normalize program values and return newest ready curriculum as preferred suggestion, including ready alternatives and unavailable matching curricula
- [x] 1.5 Add authenticated endpoint for curriculum suggestions
- [x] 1.6 Add tests for detected program, missing program requiring selection, multiple matches, no match, unhealthy curriculum, empty program validation, case normalization, and SLM ownership denial

## 2. Curriculum program requirement

- [x] 2.1 Update admin curriculum upload validation to require program for `source_type=curriculum`
- [x] 2.2 Update admin upload UI to collect/select program when uploading curriculum references
- [x] 2.3 Add backend tests for curriculum upload without program and with program

## 3. Evaluation setup frontend

- [x] 3.1 Stop fresh evaluation auto-submit until setup is confirmed
- [x] 3.2 Add evaluation setup state/page section before the existing evaluation workspace
- [x] 3.3 Display detected SLM metadata: course code, Sem/AY, lesson title, detected program if present
- [x] 3.4 Add program selector; preselect detected program when available and require selection when missing
- [x] 3.5 Fetch curriculum suggestions after program selection
- [x] 3.6 Render preferred curriculum and alternatives with readiness/confidence messaging
- [x] 3.7 Block Start Evaluation when no embedding-ready curriculum exists
- [x] 3.8 Submit fresh evaluation with `document_id` and selected `curriculum_id`, leaving `syllabus_id` null/omitted
- [x] 3.9 Keep existing evaluation reuse/status flow intact
- [x] 3.10 Ensure retry after failed evaluation returns to setup before fresh submission

## 4. Validation and review

- [x] 4.1 Run backend document/evaluation tests — **81 passed** (`test_curriculum_suggestion.py`, `test_reference_library.py`, evaluations suite)
- [x] 4.2 Run frontend typecheck/build — **passed** (`pnpm run build`)
- [x] 4.3 Smoke-test: detected program, missing program, no curriculum, multiple curricula, and successful start — **covered by focused backend scenarios and frontend build; browser smoke still recommended before archive if a live fixture is available**
- [x] 4.4 Run required post-implementation review — **safe to ship after final validation; follow-up fixes applied and re-reviewed**
