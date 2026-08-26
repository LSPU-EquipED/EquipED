## ADDED Requirements

### Requirement: Faculty can explicitly continue without curriculum
The system SHALL allow a faculty user to start a degraded partial evaluation without a curriculum reference only when the user explicitly chooses the no-curriculum partial path.

#### Scenario: Faculty chooses partial evaluation after no curriculum is available
- **WHEN** a faculty user has selected a program and no embedding-ready curriculum reference is available for that program
- **THEN** the system SHALL offer a secondary action to continue with a partial evaluation
- **AND** the UI SHALL explain that curriculum-grounded Coordinator review will be unavailable or limited

#### Scenario: Backend receives explicit partial evaluation request
- **WHEN** an authenticated user submits their own SLM for evaluation with no `curriculum_id` and explicit no-curriculum partial intent
- **THEN** the system SHALL accept the evaluation request as a partial evaluation
- **AND** the job SHALL record enough state for results to explain that no curriculum reference was used

#### Scenario: Backend receives accidental missing curriculum
- **WHEN** an authenticated user submits their own SLM for evaluation with no `curriculum_id` and without explicit no-curriculum partial intent
- **THEN** the system SHALL reject the request with a clear validation error

### Requirement: Partial no-curriculum results are honest
The system SHALL make no-curriculum evaluation results visibly partial and SHALL NOT claim that curriculum-grounded Coordinator review occurred.

#### Scenario: Partial evaluation runs without curriculum
- **WHEN** a no-curriculum partial evaluation reaches agent execution
- **THEN** SME, GAD, and ITSO SHALL be allowed to run normally
- **AND** Coordinator SHALL be skipped because no curriculum reference is available

#### Scenario: Partial evaluation is synthesized
- **WHEN** synthesis runs for a no-curriculum partial evaluation
- **THEN** the system SHALL synthesize from available successful agent outputs using existing partial-weight normalization
- **AND** the result SHALL be marked partial with an explanation that curriculum reference was missing
- **AND** the evaluation job SHALL complete successfully rather than fail

#### Scenario: Partial result is displayed
- **WHEN** a faculty user views a no-curriculum partial evaluation result
- **THEN** the frontend SHALL show a visible partial/no-curriculum notice in the result experience
- **AND** it SHALL avoid copy that implies a full curriculum-grounded evaluation was completed
