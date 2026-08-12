## Purpose

Define the Layer 3 multi-agent evaluation workflow and its bounded responsibilities.

## Requirements

### Requirement: Layer 3 coordinates specialist agents
The system SHALL run the multi-agent evaluation workflow as Layer 3 after pre-agent processing completes.

#### Scenario: Layer 3 begins from an evaluation job
- **WHEN** an evaluation job reaches the multi-agent phase
- **THEN** the system SHALL orchestrate the supported specialist agents for the job

### Requirement: Layer 3 produces structured outputs
The system SHALL collect the agent outputs needed for later inspection and persistence.

#### Scenario: Agent outputs are gathered
- **WHEN** Layer 3 agents finish their work
- **THEN** the system SHALL return structured outputs for persistence

### Requirement: Layer 3 stops before report generation
The system SHALL end the workflow after Layer 3 output collection and persistence responsibilities, without entering report generation or completion logic.

#### Scenario: Workflow ends honestly
- **WHEN** Layer 3 finishes
- **THEN** the system SHALL not perform Layer 4 report generation, scorecard completion, monitoring matrix updates, or `COMPLETED` state emission


### Requirement: Layer 3 execution reaches terminal deterministic synthesis
After Layer 3 agents complete and outputs persist, the system SHALL run deterministic Layer 4 synthesis and write the monitoring matrix as the terminal automated output. No Layer 5 SHALL run.

#### Scenario: Layer 4 terminal
- **WHEN** Layer 3 persistence succeeds
- **THEN** deterministic synthesis writes the matrix and the workflow stops
