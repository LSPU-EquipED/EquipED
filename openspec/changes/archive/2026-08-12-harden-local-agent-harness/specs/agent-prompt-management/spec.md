## MODIFIED Requirements

### Requirement: Prompt attribution reflects consumed managed text
The system SHALL persist a prompt ID only when the exact managed prompt text affects outbound model input. SME SHALL use a new extraction-only managed preamble for grouped and criterion-fallback calls; historical prompt migrations SHALL remain immutable. Coordinator SHALL remain non-consuming and persist no prompt ID until a compatible fact-only prompt contract is separately added.

#### Scenario: Unconsumed Coordinator prompt
- **WHEN** Coordinator runs without a compatible managed fact-only contract
- **THEN** it sends no managed prompt and persists no prompt ID

#### Scenario: SME forward migration
- **WHEN** the SME extraction preamble is seeded
- **THEN** a new forward migration creates it without changing historical prompt rows
