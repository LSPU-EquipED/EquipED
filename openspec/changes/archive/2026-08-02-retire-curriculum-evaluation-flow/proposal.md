## Why

EquipED is reducing its active reference scope. The existing curriculum corpus
must be removed completely from relational storage, Chroma, and local uploads,
while preserving historical evaluation records. New faculty evaluations must
remain honest and usable without curriculum grounding.

## What Changes

- Add a guarded, idempotent maintenance purge that removes curriculum source
  documents, chunks, vectors, and local PDFs only after strict cross-store
  preflight checks; historical evaluation outputs remain intact and their
  `curriculum_id` links are cleared without relabelling completed results.
- **BREAKING** Retire curriculum and rubric PDF ingestion. Admin Ingestion will
  accept only syllabus and policy documents; direct backend upload requests for
  retired source types are rejected for every role.
- Retire curriculum suggestion, selection, preview, rebuild, and recovery
  actions from the active evaluation and reference-library flows. Syllabus
  references remain library-managed but do not silently replace curriculum
  grounding.
- Make every new faculty evaluation an explicitly confirmed no-curriculum
  partial evaluation. The user confirms their program, acknowledges the
  degraded path, and the Coordinator is excluded before dispatch.
- Persist confirmed program context for new partial evaluation jobs so the
  decision is auditable and direct API callers cannot bypass it.
- Restrict the faculty upload route to faculty users, retain server-side SLM-only
  enforcement, and automatically navigate a successful processed SLM upload to
  its evaluation setup page exactly once.
- Preserve Admin SLM upload for Model Validation, preserve historical full
  evaluations, and leave rubric-table data untouched.

## Capabilities

### New Capabilities

- `curriculum-retirement-maintenance`: Defines the maintenance-mode,
  cross-store curriculum purge and verification contract.

### Modified Capabilities

- `upload-rbac`: Restricts document ingestion to SLM for faculty and syllabus
  or policy for Admin Ingestion, retiring curriculum and rubric PDF upload.
- `reference-library`: Removes curriculum documents from active library,
  preview, rebuild, and lifecycle behavior.
- `program-confirmed-curriculum-selection`: Replaces curriculum selection with
  confirmed-program, explicit partial-evaluation setup.
- `partial-evaluation-without-curriculum`: Makes the explicit no-curriculum
  path the only new faculty evaluation path while preserving historical truth.
- `evaluations`: Records confirmed program context and enforces partial-only
  submission after curriculum retirement.
- `document-dashboard-integration`: Redirects a successful faculty SLM upload
  to evaluation setup instead of the dashboard.
- `custom-semantic-document-chunking`: Removes curriculum/rubric PDF ingestion
  and embedding assumptions.
- `curriculum-reference-extraction`: Retires the active curriculum extraction
  workflow.
- `model-validation`: Removes active curriculum suggestion/selection from new
  validation runs while retaining Admin SLM upload.

## Impact

- Backend: document source validation, evaluation schemas/models/orchestration,
  maintenance command, Chroma/file cleanup, migrations, and tests.
- Client: Admin Ingestion choices, faculty route guard, upload redirect,
  program-confirmed partial setup, and retired curriculum UI/actions.
- Data: one preflighted curriculum document currently has four chunks and one
  completed linked evaluation; the evaluation is retained with its link cleared.
- No new external dependencies. This is irreversible except through an approved
  temporary backup restore.
