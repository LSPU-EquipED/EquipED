## Context

The active corpus contains one curriculum document (`CS-IT`, BSCS), four chunks,
and one completed evaluation link. Preflight found no curriculum-backed flags
and no non-terminal linked jobs. Curriculum vectors share `col_reference_all`
with syllabus vectors, so collection deletion is unsafe.

The current delete path is intentionally permissive for ordinary Admin actions:
it tolerates missing Chroma/files and commits SQL last. That is not sufficient
for a requested cross-store erasure. At the same time, removing curriculum
intake means all future faculty evaluations lack Coordinator grounding.

## Goals / Non-Goals

**Goals:**

- Retire curriculum and rubric PDF ingestion without deleting rubric-table data.
- Purge curriculum sources from SQL, Chroma, and local files without damaging
  syllabus vectors or historical evaluation results.
- Make the only new faculty path an auditable, explicitly confirmed partial
  evaluation and direct a successful SLM upload into that setup.
- Preserve Admin SLM upload for Model Validation.

**Non-Goals:**

- Redacting historical generated evaluation prose that may quote curriculum.
- Replacing curriculum with syllabus as Coordinator evidence.
- Altering past result status/partialness merely because its curriculum link is
  removed.
- Making the rubric editor persistent or changing its rubric-table data.

## Decisions

### Strict maintenance command, not a normal delete or Alembic revision

A dedicated idempotent maintenance command owns the purge. It has a dry-run
default and an explicit execute flag. It creates a content-free manifest of
document/chunk IDs, paths, counts, and hashes; validates database, Chroma, and
upload-root reachability; and refuses to run with active curriculum ingestion or
linked non-terminal evaluations.

It deletes only `document_id`-scoped curriculum vectors from `col_reference_all`,
then validates/removes PDF paths within the upload root, then performs one SQL
transaction to clear affected `evaluation_jobs.curriculum_id`, clear any nullable
flag chunk pointer to affected chunks, remove chunks, and remove documents.
Missing assets are acceptable only after their backing store is known reachable;
I/O, permission, symlink, duplicate-path, Chroma, or SQL failures abort.

This is preferred over an Alembic data migration because external Chroma/files
cannot participate in a database transaction. It is preferred over the normal
reference delete endpoint because the purge must fail closed and retain a retry
manifest.

### Retire intake while retaining legacy read compatibility

New direct upload requests reject `curriculum` and every `rubric_*` source type
for all roles. The source-type vocabulary and curriculum collection mapping stay
available during the maintenance release solely to locate and purge legacy data;
they are not accepted as new ingestion inputs. Syllabus and policy remain Admin
Ingestion inputs; faculty remains SLM-only. Admin SLM upload remains available
for Model Validation outside Admin Ingestion.

### Partial-only new evaluations require persisted confirmation

`EvaluationJob` receives nullable `confirmed_program`. New no-curriculum jobs
must carry an allowed program plus explicit `partial_without_curriculum=true`.
The backend rejects absent confirmation even when an SLM has detected metadata.
The frontend displays detected metadata as a suggestion, requires a separate
faculty confirmation, and requires acknowledgement before submission.

The Supervisor excludes Coordinator before dispatch and synthesis remains forced
partial. Historical jobs retain their original `partial_without_curriculum` value
even after their curriculum foreign key is cleared.

### Navigate after the resolved upload response

The faculty form invalidates document cache and navigates exactly once from the
awaited successful `uploadDocument` result only when it is `PROCESSED`. The
destination is `/documents/{documentId}/evaluation`; it resolves existing jobs
or renders the setup, and never auto-submits. Failed or duplicate uploads do not
navigate. `/upload` receives a faculty route guard; the backend endpoint remains
role/source-type gated rather than faculty-only.

## Risks / Trade-offs

- **Cross-store partial cleanup** → maintenance mode, manifest, strict pre/post
  verification, and idempotent rerun rather than a best-effort endpoint.
- **Shared Chroma collection** → delete by curriculum document ID only and
  verify unaffected syllabus vectors before/after.
- **Historical truth rewritten** → clear only nullable FK links; preserve result
  rows, outputs, and persisted partial state.
- **Coordinator accidentally runs SLM-only** → backend requires explicit partial
  intent and excludes Coordinator before agent dispatch.
- **Direct client/API bypass of program confirmation** → persist and validate
  `confirmed_program` server-side.
- **Redirect hides a failed upload** → navigate only from a processed response;
  retain error summary otherwise.

## Migration Plan

1. Add source-type denial, partial-only submission validation, confirmed-program
   schema, and UI removal/redirect behavior with regression tests.
2. Deploy code while retaining legacy cleanup mapping; stop app workers and
   perform maintenance preflight against the target PostgreSQL/Chroma/uploads.
3. Run the execute purge, verify zero curriculum SQL/vector/file assets and
   unchanged historical-result cardinality, then restart application instances.
4. Validate a new faculty upload redirects to setup and completes only after
   program confirmation plus partial acknowledgement. Rollback requires the
   approved temporary backup; do not infer rollback from SQL alone.

## Open Questions

- Temporary backup retention and destruction timing are operator-controlled and
  must be approved before executing the irreversible purge.
