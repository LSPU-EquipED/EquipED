## ADDED Requirements

### Requirement: Evaluation results retain agent runtime provenance
The system SHALL retain bounded per-agent runtime provenance needed to explain an evaluation result without exposing sensitive evaluation input.

#### Scenario: Agent completes after a runtime variation
- **WHEN** an agent completes using a fallback model, JSON repair, or trimmed evaluation context
- **THEN** the persisted agent result SHALL identify the actual served model and applicable runtime indicators
- **AND** authorized result consumers SHALL be able to distinguish this provenance from raw evaluation content

#### Scenario: Historical result lacks provenance
- **WHEN** an authorized user retrieves an evaluation created before runtime provenance was available
- **THEN** the system SHALL continue to return the historical result successfully
- **AND** SHALL represent unavailable provenance as absent rather than inventing it
