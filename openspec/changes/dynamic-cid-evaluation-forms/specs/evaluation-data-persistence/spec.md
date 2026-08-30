## MODIFIED Requirements

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
