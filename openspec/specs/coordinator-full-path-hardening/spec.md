# coordinator-full-path-hardening Specification

## Purpose
Canonical contract for coordinator-full-path-hardening.

## Requirements

### Requirement: Dormant full Coordinator path is authoritative and bounded
Full mode SHALL require a curriculum ID and non-empty authoritative precomputed curriculum, consume it without independent retrieval or fallback, validate exact bounded alignment rows and grounded positive evidence, and use deterministic summary/merge attribution. Missing runtime curriculum or Coordinator failure SHALL fail a requested full job; only explicit partial intent may complete partial. The Coordinator SHALL remain dormant for ordinary no-curriculum submissions. All generated Coordinator evaluation outputs SHALL remain human-advisory and preserve local data residency.

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

### Requirement: Claim-level curriculum grounding rejection and normalization
The Coordinator SHALL validate positive alignment claims against authoritative curriculum text using exact nonempty substring matching. Structurally valid positive claims lacking an exact nonempty curriculum substring SHALL be normalized to false with empty evidence, incrementing deterministic rejection attribution counters without LLM retries or independent full fallback calls. Invalid keys, malformed types, missing or duplicate criterion identity, or cardinality mismatches SHALL NOT be normalized and SHALL fail closed.

#### Scenario: Structurally valid positive without exact nonempty curriculum substring
- **WHEN** a Coordinator alignment row provides a structurally valid positive claim whose evidence is not an exact nonempty substring of the authoritative curriculum text
- **THEN** the positive claim is normalized to false with empty evidence, the rejection is counted in deterministic attribution metadata, no retry is performed, and processing continues across exact rows

#### Scenario: All claims rejected yields valid all-false score 1
- **WHEN** all positive claims across all curriculum alignment rows fail grounding and are normalized to false with empty evidence
- **THEN** the result is evaluated as a valid all-false alignment scoring 1 through deterministic scoring, preserving human-advisory truth

#### Scenario: Structural, type, identity, or cardinality violation fails closed
- **WHEN** Coordinator output contains invalid keys, malformed data types, missing or duplicate criterion identities, or incorrect row cardinality
- **THEN** normalization is bypassed, the Coordinator agent fails closed, and the full evaluation job terminates `FAILED`

### Requirement: Coordinator objective compatibility shape
The Coordinator parser SHALL accept objective items formatted either entirely as canonical `{id, text}` objects or entirely as exact alias `{objective_id, objective, curriculum_alignment, evidence}` objects. When alias objects are supplied, any nested alias `curriculum_alignment` or `evidence` fields SHALL be ignored in favor of the authoritative top-level curriculum alignment rows. The parser SHALL reject mixed formats, unknown fields, or missing required identifier and text keys, failing closed before scoring or normalization.

#### Scenario: Canonical objective shape is supplied
- **WHEN** objectives are provided as a list where every item matches canonical `{id, text}`
- **THEN** the Coordinator SHALL parse the objectives and evaluate alignment using top-level curriculum alignment rows

#### Scenario: Exact alias objective shape is supplied
- **WHEN** objectives are provided as a list where every item matches exact alias `{objective_id, objective, curriculum_alignment, evidence}`
- **THEN** the Coordinator SHALL map `objective_id` to id and `objective` to text, ignore any nested alignment/evidence values, and evaluate alignment using authoritative top-level rows

#### Scenario: Mixed or malformed objective shapes are supplied
- **WHEN** objectives contain a mixture of canonical and alias shapes, missing required keys, or unknown fields
- **THEN** the Coordinator SHALL fail closed and the full evaluation job SHALL terminate `FAILED`
