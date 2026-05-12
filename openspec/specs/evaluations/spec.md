# evaluations Specification

## Purpose
Define the evaluation job contract for the current phase, limited to safe pre-agent processing, honest failure at the unimplemented Layer 3 boundary, and ownership-scoped polling.

## Requirements

### Requirement: Evaluation jobs advance through the safe pre-agent boundary
The system SHALL support evaluation job submission and progress through the pre-agent lifecycle stages without implying that multi-agent evaluation is already available.

#### Scenario: Evaluation job is accepted and begins processing
- **WHEN** an authenticated user submits a new evaluation request for a document they own
- **THEN** the system SHALL create an evaluation job in `SUBMITTED` state and continue into the pre-agent processing stages

#### Scenario: Pre-agent lifecycle remains explicit
- **WHEN** an evaluation job is running before Layer 3 agent execution
- **THEN** the system SHALL represent progress using the existing lifecycle states up to `EVALUATING` and SHALL not skip directly to a completed result

### Requirement: Evaluation fails honestly at the unimplemented Layer 3 boundary
The system SHALL terminate evaluation jobs with a clear failure when execution reaches the currently unimplemented Layer 3 multi-agent boundary.

#### Scenario: Layer 3 execution is not available yet
- **WHEN** a job reaches the point where multi-agent evaluation would begin
- **THEN** the system SHALL mark the job as `FAILED` and record a failure reason that explains the Layer 3 boundary is not implemented

#### Scenario: Failure is terminal rather than silent
- **WHEN** Layer 3 cannot continue
- **THEN** the system SHALL not leave the job in an ambiguous in-progress state or present a fabricated success outcome

### Requirement: Evaluation polling is limited to the owning user
The system SHALL only expose evaluation status for jobs owned by the authenticated user who is polling them.

#### Scenario: User polls their own job
- **WHEN** an authenticated user requests the status of an evaluation job they created
- **THEN** the system SHALL return that job's current state and progress information

#### Scenario: User attempts to poll another user's job
- **WHEN** an authenticated user requests the status of an evaluation job owned by a different user
- **THEN** the system SHALL deny access and SHALL not disclose the other job's status
