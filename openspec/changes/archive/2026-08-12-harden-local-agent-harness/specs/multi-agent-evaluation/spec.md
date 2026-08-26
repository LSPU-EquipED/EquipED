## MODIFIED Requirements

### Requirement: Layer 3 execution reaches terminal deterministic synthesis
After Layer 3 agents complete and outputs persist, the system SHALL run deterministic Layer 4 synthesis and write the monitoring matrix as the terminal automated output. No Layer 5 SHALL run.

#### Scenario: Layer 4 terminal
- **WHEN** Layer 3 persistence succeeds
- **THEN** deterministic synthesis writes the matrix and the workflow stops
