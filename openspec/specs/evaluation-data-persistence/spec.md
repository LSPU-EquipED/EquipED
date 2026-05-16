## Purpose

Define how evaluation job outputs are persisted for auditability and downstream inspection.

## Requirements

### Requirement: Layer 3 outputs are persisted as job data
The system SHALL persist evaluation outputs produced during Layer 3 before the workflow stops.

#### Scenario: Raw outputs are stored
- **WHEN** Layer 3 emits agent outputs
- **THEN** the system SHALL store the outputs with the owning evaluation job

### Requirement: Persistence remains scoped to the owning user
The system SHALL keep persisted evaluation data associated with the authenticated user who owns the job.

#### Scenario: Persisted data belongs to the job owner
- **WHEN** evaluation data is saved
- **THEN** the stored records SHALL reference the job owner and remain inaccessible to other users

### Requirement: Persistence does not create downstream artifacts
The system SHALL persist outputs without generating reports, scorecards, or matrix updates.

#### Scenario: No derived report is written
- **WHEN** Layer 3 data is saved
- **THEN** the system SHALL not create a report or complete a scorecard as part of persistence
