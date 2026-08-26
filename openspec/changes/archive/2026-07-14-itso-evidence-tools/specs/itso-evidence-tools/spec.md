## ADDED Requirements

### Requirement: ITSO retrieves trusted local policy evidence by criterion area
The system SHALL allow the ITSO evaluation path to retrieve bounded local policy clauses for intellectual-property/ownership, data-privacy/confidentiality, and academic-rights evidence. Retrieval SHALL derive an allowlist of healthy active policy document IDs from SQL and filter the dedicated policy collection by both policy area and that allowlist. Policy evidence SHALL remain local to EquipED-controlled storage and SHALL be advisory input to human-reviewed evaluation.

#### Scenario: Matching policy evidence is available
- **WHEN** ITSO pre-dispatch preparation has healthy local policy documents for a criterion area
- **THEN** the system SHALL retrieve a bounded, deterministic set of clause-oriented policy chunks from the matching policy area
- **AND** include their bounded identifiers and content in the frozen ITSO evidence snapshot

#### Scenario: Orphaned policy vectors exist
- **WHEN** a policy Chroma vector has no matching healthy active SQL document, stored chunks, or local PDF
- **THEN** the system SHALL exclude that vector from ITSO policy evidence

#### Scenario: Policy evidence is unavailable
- **WHEN** no healthy local policy document is available for an ITSO criterion area or retrieval fails
- **THEN** the system SHALL record an explicit unavailable evidence state for that area
- **AND** the ITSO result SHALL NOT assert policy noncompliance solely because policy evidence is unavailable

### Requirement: ITSO evidence tool outcomes are persisted safely
The system SHALL persist bounded ITSO policy-retrieval outcomes in the ITSO provenance envelope without persisting raw SLM content, raw prompts, policy clauses, or policy document IDs. The system SHALL sanitize recursively at both successful and failed ITSO persistence boundaries.

#### Scenario: ITSO result is persisted with evidence tool outcomes
- **WHEN** an ITSO result is stored after policy retrieval
- **THEN** provenance SHALL include allowlisted policy availability/retrieval indicators, bounded policy hashes, and tool-version/configuration indicators
- **AND** the stored provenance SHALL remain readable through authorized evaluation result responses

#### Scenario: Historical result has no evidence tool provenance
- **WHEN** an authorized user retrieves an ITSO result created before evidence tools were available
- **THEN** the system SHALL return the result successfully with absent evidence-tool provenance

### Requirement: Policy evidence delivery is residency-gated
The system SHALL deliver retrieved policy clauses to an ITSO prompt only when the configured LLM backend is institutionally approved and local/self-hosted. When policy delivery is disabled by residency configuration, the system SHALL retain explicit unavailable evidence states and SHALL NOT fail the evaluation.

#### Scenario: Policy delivery uses an external LLM backend
- **WHEN** the configured ITSO LLM backend is not institutionally approved and local/self-hosted
- **THEN** the system SHALL NOT add policy clause text to the ITSO prompt
- **AND** provenance SHALL record the policy-delivery-unavailable state

### Requirement: Policy documents require a recognized area
The system SHALL require every `policy` document to have exactly one recognized policy area and SHALL require non-policy documents to have no policy area. This invariant SHALL be enforced by application validation and database constraints.

#### Scenario: Invalid policy classification is submitted
- **WHEN** a policy upload has no recognized policy area or a non-policy upload supplies a policy area
- **THEN** the system SHALL reject the upload before file persistence
