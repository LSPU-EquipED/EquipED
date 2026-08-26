## ADDED Requirements

### Requirement: Dormant full Coordinator path is authoritative and bounded
Full mode SHALL require a curriculum ID and non-empty authoritative precomputed curriculum, consume it without independent retrieval or fallback, validate exact bounded alignment rows and grounded positive evidence, and use deterministic summary/merge attribution. Missing runtime curriculum or Coordinator failure SHALL fail a requested full job; only explicit partial intent may complete partial. The Coordinator SHALL remain dormant for ordinary no-curriculum submissions.

#### Scenario: Full job lacks curriculum
- **WHEN** full mode is requested without authoritative precomputed curriculum
- **THEN** Coordinator fails, available agents are persisted, synthesis is partial, and the job terminates `FAILED`

#### Scenario: Explicit partial submission
- **WHEN** no-curriculum partial intent is explicit
- **THEN** Coordinator is skipped and the job completes with `COMPLETED_PARTIAL` matrix status

### Requirement: Coordinator merge and attribution are exact
Coordinator SHALL validate exact ten-criterion identity and uniqueness before merge. A valid curriculum row with all false indicators SHALL score 1. Coordinator SHALL emit no managed prompt attribution, independent full fallback, or LLM summary.

#### Scenario: Invalid merge identity
- **WHEN** curriculum alignment rows omit, duplicate, or introduce a criterion
- **THEN** Coordinator fails closed before scoring
