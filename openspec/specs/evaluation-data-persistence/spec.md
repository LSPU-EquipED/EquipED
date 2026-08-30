# evaluation-data-persistence Specification

## Purpose

Define how evaluation job outputs are persisted for auditability and downstream inspection.

## Requirements

### Requirement: Layer 3 outputs are persisted as job data
The system SHALL persist evaluation outputs produced during Layer 3 before the workflow stops, including the exact agent form revision, canonical form snapshot payload hash, adapter key, adapter version, `form_snapshot_id` on `agent_results`, and criterion score bindings whose existing `criterion_id` field is the exact snapshot `criterion_code`. Dynamic domain and criterion order SHALL be reconstructed from the verified immutable form snapshot payload, and persisted scores SHALL match exact snapshot criterion codes; missing, duplicate, or extra criterion scores SHALL fail closed.

Authenticated owner-scoped faculty evaluation endpoints SHALL return a single explicit allowlisted snapshot presentation DTO containing:
- Snapshot and form identity: `form_snapshot_id`, `rubric_set_id`, and form `version`
- Revision and adapter identity: `snapshot_hash`, `adapter_key`, and `adapter_version`
- Ordered domain and criterion definitions: criterion UUID, criterion code, criterion title, criterion description, domain name, domain display order, and criterion display order
- Scorecard presentation fields: criterion score, justification, evidence, and ungrounded flags

Faculty presentation DTOs SHALL strictly exclude `strategy_config`, `scoring_rule`/guidance, prompt/raw/group response data, and unrestricted provenance. Full snapshot strategy configurations SHALL remain restricted to admin-authorized endpoints.

#### Scenario: Raw outputs are stored
- **WHEN** Layer 3 emits agent outputs
- **THEN** the system SHALL store the outputs with the owning evaluation job alongside the immutable form snapshot bindings and criterion score records

#### Scenario: Faculty result uses allowlisted presentation DTO
- **WHEN** an authenticated faculty user views a completed evaluation result
- **THEN** the API SHALL return the allowlisted snapshot presentation DTO with form/revision/adapter identity, ordered domain/criterion definitions, and scorecard fields
- **AND** SHALL NOT expose internal strategy_config, scoring_rule/guidance, raw prompt/response data, or unrestricted provenance

#### Scenario: Mismatched or incomplete criterion score persistence fails closed
- **WHEN** persisted agent scores contain missing, duplicate, unknown, or extra criterion codes compared to the bound snapshot
- **THEN** persistence SHALL fail closed and reject result persistence

### Requirement: Persistence remains scoped to the owning user
The system SHALL keep persisted evaluation data associated with the authenticated user who owns the job.

#### Scenario: Persisted data belongs to the job owner
- **WHEN** evaluation data is saved
- **THEN** the stored records SHALL reference the job owner and remain inaccessible to other users

### Requirement: Persistence does not create downstream artifacts
The system SHALL persist outputs without generating reports, scorecards, or matrix updates.

#### Scenario: No derived report is written
- **WHEN** Layer 3 data is saved
- **THEN** the system SHALL not create a report or complete a scorecard as part of persistence

### Requirement: Evaluation outputs are persisted with bounded privacy
Layer 3 outputs SHALL remain ownership-scoped and SHALL be persisted before deterministic terminal Layer 4 matrix synthesis. Raw ITSO model output SHALL NOT be persisted; only normalized results and bounded metadata may be stored.

#### Scenario: ITSO raw response
- **WHEN** an ITSO response is accepted or rejected
- **THEN** persistence contains no raw response, prompt, policy clause, or SLM text
