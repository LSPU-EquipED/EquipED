# partial-evaluation-without-curriculum Specification

## Purpose
Define the explicit degraded evaluation path used when no ready curriculum reference exists, while keeping full curriculum-grounded evaluation honest and distinct.

## Requirements

### Requirement: Faculty can explicitly continue without curriculum
The system SHALL provide explicitly confirmed no-curriculum partial evaluation as a fallback when faculty do not select a ready matching curriculum. It SHALL require confirmed program context and a dedicated client-side partial acknowledgement before enabling submission. The acknowledged request SHALL be represented by explicit `partial_without_curriculum=true`; no separate acknowledgement column is required. The acknowledgement SHALL NOT be required for a valid full-intent request.

#### Scenario: Faculty confirms a new partial evaluation
- **WHEN** a faculty user confirms a program, selects the no-curriculum option, and acknowledges the warning for their processed SLM
- **THEN** the system SHALL accept an explicit partial request and persist the confirmed program

#### Scenario: Faculty selects full evaluation
- **WHEN** a faculty user selects a ready matching curriculum
- **THEN** the system SHALL not require the no-curriculum acknowledgement

#### Scenario: Backend receives incomplete partial request
- **WHEN** a no-curriculum request lacks partial intent, confirmed program context, or client acknowledgement state required to enable submission
- **THEN** the system SHALL reject or prevent it without creating an evaluation

### Requirement: Partial no-curriculum results are honest
The system SHALL visibly mark no-curriculum results partial and SHALL skip Coordinator before dispatch. Historical completed evaluations SHALL preserve their original partial/full state even if a curriculum link is later cleared.

#### Scenario: New partial evaluation executes
- **WHEN** a confirmed no-curriculum evaluation reaches agent execution
- **THEN** SME, GAD, and ITSO SHALL run, Coordinator SHALL be excluded, and synthesis SHALL use partial-weight normalization

#### Scenario: Historical curriculum link is cleared
- **WHEN** maintenance clears a nullable curriculum link from a completed historical evaluation
- **THEN** the system SHALL preserve the job's persisted partial/full status and outputs
