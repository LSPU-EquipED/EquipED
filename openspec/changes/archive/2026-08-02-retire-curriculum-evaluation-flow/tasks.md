## 1. Safety and Data-Retirement Foundation

- [x] 1.1 Add a maintenance-mode curriculum purge command with dry-run default, explicit execute confirmation, content-free manifest, and idempotent reporting.
- [x] 1.2 Implement strict database, Chroma, upload-root, active-ingestion, active-job, vector, file-path, and flag-reference preflight checks.
- [x] 1.3 Implement scoped curriculum vector/file cleanup and one SQL transaction that clears permitted links and removes curriculum chunks/documents without modifying historical result state.
- [x] 1.4 Add purge failure, retry, historical-preservation, shared-syllabus-vector, unsafe-path, and PostgreSQL-FK regression tests.

## 2. Retire Curriculum and Rubric PDF Intake

- [x] 2.1 Restrict server-side document upload validation to active source types: faculty SLMs; Admin Ingestion syllabus/policy; retain Admin SLM support for Model Validation.
- [x] 2.2 Remove curriculum/rubric PDF choices, lifecycle actions, routes, and suggestion/rebuild behavior from active Admin Ingestion and Reference Library flows while retaining legacy cleanup support for the purge.
- [x] 2.3 Update document/reference tests to prove retired source types fail before extraction, chunking, or embedding and active types retain their current access rules.

## 3. Confirmed Partial Evaluation Contract

- [x] 3.1 Add nullable persisted confirmed-program context with an Alembic migration that leaves historical jobs unchanged.
- [x] 3.2 Require explicit partial intent and valid confirmed program for every new faculty evaluation; reject accidental/direct API bypasses.
- [x] 3.3 Remove active curriculum suggestion/selection from evaluation and Model Validation flows; preserve existing historical result rendering and truthful Coordinator handling.
- [x] 3.4 Ensure Supervisor excludes Coordinator before dispatch and synthesis remains deliberately partial for all new curriculum-retired evaluations.
- [x] 3.5 Add backend regression tests for submission, execution, recovery, historical rows with cleared links, and Model Validation partial expectations.

## 4. Faculty Upload-to-Evaluation Flow

- [x] 4.1 Apply a faculty-only route guard to `/upload` while preserving server-side source-type enforcement and Admin upload workflows.
- [x] 4.2 Navigate exactly once from a successful processed SLM upload to `/documents/{documentId}/evaluation`; retain error/duplicate safeguards and document cache invalidation.
- [x] 4.3 Rework evaluation setup to show detected program as a suggestion, require separate confirmation, require partial acknowledgement, and never auto-submit.
- [x] 4.4 Add focused client tests for redirect, guard, confirmation, partial acknowledgement, failure, and existing-evaluation reuse paths.

## 5. Controlled Purge and Verification

- [x] 5.1 Confirm no application worker is active and run the maintenance command dry-run against the target PostgreSQL, Chroma, and upload root. (User explicitly waived a temporary database snapshot for this one-reference cleanup.)
- [x] 5.2 Execute the curriculum purge only after dry-run verification; retain historical evaluation outputs and record the final manifest summary.
- [x] 5.3 Verify zero curriculum SQL rows/chunks/vectors/files; verify syllabus, policy, SLM, rubric-table, historical evaluation, model-validation, and matrix records remain intact.
- [ ] 5.4 Run backend tests, client tests, lint/typecheck/build, OpenSpec validation, and a manual faculty upload-to-confirmed-partial-evaluation smoke test.
