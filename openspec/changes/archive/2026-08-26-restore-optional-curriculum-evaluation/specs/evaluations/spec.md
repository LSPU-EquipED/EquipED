## REMOVED Requirements

### Requirement: New curriculum-retired evaluations require confirmed partial context
**Reason**: Curriculum ingestion and optional full evaluation are active again for BSCS and BSInfoTech; partial intent is no longer the only valid launch mode.

**Migration**: Replaced by `New evaluations require explicit confirmed curriculum intent` below. Existing job rows remain unchanged.

## ADDED Requirements

### Requirement: New evaluations require explicit confirmed curriculum intent
The system SHALL require an explicit confirmed canonical program write value (`BSCS` or `BSInfoTech`) and one of two non-conflicting intents: full intent with a matching ready curriculum ID and explicit `partial_without_curriculum=false`, or partial intent with no curriculum ID and explicit `partial_without_curriculum=true`. `BSIT` SHALL remain a read alias only and SHALL be rejected on evaluation writes. It SHALL reject missing or conflicting combinations without creating a job. The target lookup SHALL validate missing/foreign/non-SLM ownership with the same masked response before program and curriculum validation. Full curriculum validation SHALL use the documents-owned curriculum-readiness service rather than SQL flags alone.

#### Scenario: Full request is valid
- **WHEN** faculty submits their processed SLM with confirmed BSCS or BSInfoTech program, a ready curriculum for the same program, and partial intent disabled
- **THEN** the system SHALL create a full evaluation linked to that curriculum

#### Scenario: Partial request is valid
- **WHEN** faculty submits their processed SLM with confirmed program, no curriculum ID, and explicit partial intent
- **THEN** the system SHALL create a no-curriculum partial evaluation

#### Scenario: Request combines curriculum and partial intent
- **WHEN** a request includes a curriculum ID and sets partial intent true
- **THEN** the system SHALL reject the conflicting request without creating an evaluation

#### Scenario: Partial flag is omitted
- **WHEN** a caller omits `partial_without_curriculum`
- **THEN** the system SHALL reject the request rather than infer intent

#### Scenario: Legacy program alias is submitted
- **WHEN** a caller submits `BSIT` as confirmed program on a new evaluation
- **THEN** the system SHALL reject the write and require `BSInfoTech`

#### Scenario: Curriculum program mismatches confirmed program
- **WHEN** a full request selects a curriculum whose canonical program differs from the confirmed program
- **THEN** the system SHALL reject the request with a clear validation error

#### Scenario: Curriculum is not ready
- **WHEN** a full request selects a curriculum that is failed, unprocessed, missing chunks, or missing required local vectors
- **THEN** the system SHALL reject the request without creating an evaluation

#### Scenario: Curriculum lacks administrator provenance
- **WHEN** a full request selects a legacy curriculum row not uploaded by an administrator
- **THEN** the system SHALL reject the request without creating an evaluation

### Requirement: Full intent executes Coordinator honestly
A full-intent evaluation SHALL schedule Coordinator with authoritative curriculum text loaded before worker dispatch, SHALL retain full synthesis weights only when required outputs succeed, and SHALL terminate `FAILED` rather than automatically degrade to partial if curriculum or Coordinator becomes unavailable. A partial-intent evaluation SHALL exclude Coordinator before dispatch and SHALL complete as `COMPLETED_PARTIAL` only when every scheduled partial agent succeeds.

#### Scenario: Full evaluation succeeds
- **WHEN** authoritative curriculum text is available and SME, GAD, ITSO, and Coordinator succeed
- **THEN** deterministic synthesis SHALL produce a full completed monitoring matrix with Coordinator attribution

#### Scenario: Curriculum disappears after full submission
- **WHEN** a full-intent job reaches execution without authoritative curriculum text
- **THEN** the system SHALL preserve full intent, synthesize available outputs as applicable, and terminate the job `FAILED`

#### Scenario: Coordinator fails
- **WHEN** a requested full evaluation does not produce a successful Coordinator result
- **THEN** the system SHALL terminate `FAILED` and SHALL NOT relabel the job as partial

#### Scenario: Partial evaluation succeeds
- **WHEN** an explicit partial job's SME, GAD, and ITSO agents all succeed
- **THEN** the job SHALL complete with a `COMPLETED_PARTIAL` matrix and Coordinator SHALL remain excluded

#### Scenario: Partial evaluation agent fails
- **WHEN** an explicit partial job lacks a successful SME, GAD, or ITSO result
- **THEN** the job and matrix SHALL terminate `FAILED` while preserving partial intent
