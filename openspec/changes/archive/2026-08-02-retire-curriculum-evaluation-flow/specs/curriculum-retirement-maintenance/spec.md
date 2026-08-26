## ADDED Requirements

### Requirement: Curriculum purge fails closed across stores
The system SHALL provide an administrator-operated maintenance command that
defaults to dry-run and requires explicit execution to purge legacy curriculum
sources. It SHALL verify target database, Chroma, upload-root access, zero
curriculum ingestion, zero curriculum-linked non-terminal evaluations, and a
content-free manifest before deleting any asset.

#### Scenario: Unsafe purge preflight
- **WHEN** Chroma, the database, the upload root, or an active curriculum-linked
  job is unavailable or unsafe
- **THEN** the command SHALL abort without reporting a successful purge

### Requirement: Curriculum purge preserves historical evaluation truth
The executed purge SHALL remove curriculum document rows, chunks, scoped Chroma
vectors, and local PDFs while preserving evaluation, synthesis, validation, and
matrix rows. It SHALL clear affected nullable curriculum links and any nullable
flag chunk pointers before SQL chunk deletion, without changing a completed
job's persisted partial state.

#### Scenario: Completed evaluation references a purged curriculum
- **WHEN** a completed evaluation links to a curriculum selected for purge
- **THEN** the command SHALL retain the evaluation and its outputs, clear only
  its curriculum link, and remove the curriculum source assets
