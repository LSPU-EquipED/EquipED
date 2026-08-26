## MODIFIED Requirements

### Requirement: Monitoring matrix table
The system SHALL maintain a `monitoring_matrix` table as a materialized view of evaluation job progress. Terminal matrix status SHALL preserve launch intent: intentional partial success uses matrix `COMPLETED_PARTIAL` while the job/result retains partial intent; successful full evaluation uses matrix `COMPLETED` while the job/result retains full intent; failed full or partial evaluation uses matrix `FAILED` while the associated job/result retains its original full or partial intent. Partial intent is not a monitoring-matrix column and SHALL NOT be inferred from matrix status.

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

#### Scenario: Intentional partial evaluation completes
- **WHEN** an explicit partial job successfully completes every scheduled agent and synthesis
- **THEN** the job SHALL be `COMPLETED`, the matrix SHALL be `COMPLETED_PARTIAL`, and the job/result SHALL retain partial intent

#### Scenario: Full evaluation completes
- **WHEN** a full job successfully completes all required agents and synthesis
- **THEN** the job and matrix SHALL be `COMPLETED` and the job/result SHALL retain full intent

#### Scenario: Full evaluation fails
- **WHEN** a full job loses authoritative curriculum, lacks Coordinator output, or otherwise terminates `FAILED`
- **THEN** the matrix SHALL be `FAILED`, the job/result SHALL retain full intent, and the result SHALL NOT be labeled `COMPLETED_PARTIAL`

#### Scenario: Partial evaluation fails
- **WHEN** an intentional partial job has a failed or missing SME, GAD, or ITSO result
- **THEN** the job and matrix SHALL be `FAILED`, the job/result SHALL retain partial intent, and the matrix SHALL NOT be labeled `COMPLETED_PARTIAL`

#### Scenario: Matrix row is updated on synthesis completion
- **WHEN** a job transitions from `SYNTHESIZING` to `COMPLETED` or `FAILED`
- **THEN** the matrix row SHALL be updated with the final `synthesized_score`, `domain_scores_json`, `flag_count`, and intent-honest `evaluation_status`

#### Scenario: Ungrounded scores are flagged for review
- **WHEN** an agent returns a criterion score without grounded justification, evidence, or chunk citation recorded as ungrounded advisory output
- **THEN** synthesis SHALL persist an `evaluation_flags` row for that criterion with a reason identifying it as requiring human review
- **AND** the matrix row's `flag_count` SHALL include that flag
- **AND** the flagged criterion SHALL be surfaced for human review rather than presented as an authoritative grounded score
