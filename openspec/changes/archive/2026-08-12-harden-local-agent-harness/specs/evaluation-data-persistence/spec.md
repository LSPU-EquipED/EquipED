## MODIFIED Requirements

### Requirement: Evaluation outputs are persisted with bounded privacy
Layer 3 outputs SHALL remain ownership-scoped and SHALL be persisted before deterministic terminal Layer 4 matrix synthesis. Raw ITSO model output SHALL NOT be persisted; only normalized results and bounded metadata may be stored.

#### Scenario: ITSO raw response
- **WHEN** an ITSO response is accepted or rejected
- **THEN** persistence contains no raw response, prompt, policy clause, or SLM text
