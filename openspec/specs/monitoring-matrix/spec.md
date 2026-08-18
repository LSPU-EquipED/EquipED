# monitoring-matrix Specification

## Purpose
Define the monitoring matrix capability for admin-level oversight of evaluation jobs, including table schema, lifecycle hooks, and dashboard API.

## Requirements

### Requirement: Monitoring matrix table
The system SHALL maintain a `monitoring_matrix` table as a materialized view of evaluation job progress.

**Schema:**
- `matrix_id` (UUID, PK)
- `document_id` (UUID, FK→documents, UNIQUE)
- `evaluation_id` (UUID, FK→evaluation_jobs, nullable)
- `faculty_name` (VARCHAR 300, nullable)
- `program` (VARCHAR 300, nullable)
- `evaluation_status` (VARCHAR 50, default SUBMITTED)
- `synthesized_score` (NUMERIC 5,2, nullable)
- `domain_scores_json` (JSON, nullable) — per-domain score map
- `flag_count` (INTEGER, default 0)
- `feedback_status` (VARCHAR 50, default NO_FEEDBACK)
- `last_updated` (TIMESTAMPTZ, auto-updated)

#### Scenario: Matrix row is created on evaluation submission
- **WHEN** an evaluation job enters `SUBMITTED` status
- **THEN** a row SHALL be inserted or upserted into `monitoring_matrix` for that document

#### Scenario: Matrix row is updated on synthesis completion
- **WHEN** a job transitions from `SYNTHESIZING` to `COMPLETED` (or `FAILED`)
- **THEN** the matrix row SHALL be updated with the final `synthesized_score`, `domain_scores_json`, `flag_count`, and `evaluation_status`

#### Scenario: Ungrounded scores are flagged for review
- **WHEN** an agent returns a criterion score without grounded justification, evidence, or chunk citation (recorded as ungrounded advisory output)
- **THEN** synthesis SHALL persist an `evaluation_flags` row for that criterion with a reason identifying it as requiring human review
- **AND** the matrix row's `flag_count` SHALL include that flag
- **AND** the flagged criterion SHALL be surfaced for human review rather than presented as an authoritative grounded score

### Requirement: Admin dashboard API
The system SHALL expose a `GET /evaluations/matrix` endpoint restricted to admin users.

#### Scenario: Admin retrieves matrix with filters
- **WHEN** an admin requests `GET /evaluations/matrix`
- **THEN** the system SHALL return paginated rows from `monitoring_matrix`
- **AND** the system SHALL support optional filtering by `program` and `evaluation_status`

#### Scenario: Non-admin is denied
- **WHEN** a non-admin or unauthenticated user requests `GET /evaluations/matrix`
- **THEN** the system SHALL return 401 (unauthenticated) or 403 (non-admin)

### Requirement: Matrix upsert semantics
The system SHALL use upsert (insert or update) semantics when writing to `monitoring_matrix`, using `document_id` as the unique key.

#### Scenario: Re-evaluation updates existing row
- **WHEN** a document is re-evaluated
- **THEN** the existing matrix row SHALL be updated (not duplicated) with the new evaluation results

#### Scenario: Concurrent writes do not produce duplicates
- **WHEN** two evaluation jobs for the same document complete simultaneously
- **THEN** the system SHALL resolve the race condition using `IntegrityError` handling and retry with an update
