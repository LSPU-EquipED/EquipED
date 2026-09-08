## MODIFIED Requirements

### Requirement: Monitoring matrix table
The system SHALL maintain a `monitoring_matrix` table as a progressive, materialized view of evaluation progress per document (`UNIQUE(document_id)`). The matrix SHALL accumulate domain evaluation outputs independently as individual domain experts execute their specialist roles over time.

**Progressive Status Semantics:**
- `SUBMITTED`: Evaluation request is queued or in preparation; 0 domains evaluated.
- `IN_PROGRESS`: 1 to 3 domains (`sme`, `coordinator`, `gad`, `itso`) have completed evaluation.
- `COMPLETED`: All 4 domains have completed evaluation; the composite `synthesized_score` is finalized.
- `FAILED`: An active single-agent evaluation run failed unrecoverably.

#### Scenario: Matrix row is created on evaluation submission
- **WHEN** a single-agent evaluation job enters `SUBMITTED` status
- **THEN** a row SHALL be inserted or upserted into `monitoring_matrix` for that document

#### Scenario: Single domain evaluation completes and updates matrix progressively
- **WHEN** an evaluation job for a specific `target_agent` completes successfully
- **THEN** synthesis SHALL upsert the `monitoring_matrix` row for that document
- **AND** SHALL deep-merge the completed domain result into `domain_scores_json[target_agent]`
- **AND** SHALL update `flag_count` to include flags from this domain
- **AND** if fewer than 4 domains are completed, the matrix `evaluation_status` SHALL be `IN_PROGRESS`

#### Scenario: Fourth domain evaluation completes and finalizes matrix
- **WHEN** a single-agent evaluation completes and all 4 domains (`sme`, `coordinator`, `gad`, `itso`) are present in `domain_scores_json`
- **THEN** synthesis SHALL compute the composite `synthesized_score` using canonical `AGENT_WEIGHTS`
- **AND** the matrix `evaluation_status` SHALL transition to `COMPLETED`
- **AND** the matrix row SHALL record the final `adjectival_rating`

#### Scenario: Full evaluation completes
- **WHEN** all 4 domains have completed evaluation
- **THEN** the matrix row SHALL be `COMPLETED` and display the final composite score

#### Scenario: Full evaluation fails
- **WHEN** an evaluation job encounters an unrecoverable failure and the document has 0 completed domains
- **THEN** the matrix row SHALL transition to `FAILED`

#### Scenario: Partial evaluation fails
- **WHEN** an evaluation job for a specific domain fails but the document has existing completed domains
- **THEN** the matrix row SHALL retain its prior completed domains and record an error notice for the failed domain

#### Scenario: Intentional partial evaluation completes
- **WHEN** a single-agent evaluation completes
- **THEN** the evaluation job SHALL be `COMPLETED` and the matrix row SHALL record the completed domain

#### Scenario: Matrix row is updated on synthesis completion
- **WHEN** single-agent evaluation synthesis completes
- **THEN** the matrix row SHALL be updated with the latest `domain_scores_json`, `flag_count`, and progressive `evaluation_status`

#### Scenario: Ungrounded scores are flagged for review
- **WHEN** an agent returns a criterion score without grounded justification, evidence, or chunk citation recorded as ungrounded advisory output
- **THEN** synthesis SHALL persist an `evaluation_flags` row for that criterion with a reason identifying it as requiring human review
- **AND** the matrix row's `flag_count` SHALL include that flag
- **AND** the flagged criterion SHALL be surfaced for human review rather than presented as an authoritative grounded score
