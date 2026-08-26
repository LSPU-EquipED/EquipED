## MODIFIED Requirements

### Requirement: Faculty can explicitly continue without curriculum
The system SHALL make explicitly confirmed no-curriculum partial evaluation the
only new faculty evaluation path. It SHALL require confirmed program context and
an acknowledgement before accepting the request.

#### Scenario: Faculty confirms a new partial evaluation
- **WHEN** a faculty user confirms a program and acknowledges the no-curriculum
  warning for their processed SLM
- **THEN** the system SHALL accept an explicit partial request and persist the
  confirmed program

#### Scenario: Backend receives incomplete partial request
- **WHEN** a request lacks partial intent or confirmed program context
- **THEN** the system SHALL reject it without creating an evaluation

### Requirement: Partial no-curriculum results are honest
The system SHALL visibly mark new no-curriculum results partial and SHALL skip
Coordinator before dispatch. Historical completed evaluations SHALL preserve
their original partial/full state even if a retired curriculum link is cleared.

#### Scenario: New partial evaluation executes
- **WHEN** a confirmed no-curriculum evaluation reaches agent execution
- **THEN** SME, GAD, and ITSO SHALL run, Coordinator SHALL be excluded, and
  synthesis SHALL use partial-weight normalization
