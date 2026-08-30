## MODIFIED Requirements

### Requirement: GAD uses one normal-path grounded extraction call
The system SHALL execute one normal-path GAD LLM extraction call per evaluation job through a GAD-local fact-only execution pipeline. Active GAD managed prompts SHALL serve as criterion-agnostic framing only; fixed criterion identifiers in managed prompts SHALL fail closed, and per-criterion authority SHALL come exclusively from the pre-resolved GAD form snapshot. The call SHALL produce a duplicate-safe ordered list with exactly one named factual section for all criteria defined in the frozen, ordered GAD form snapshot. The configured strategy SHALL select the bounded section shape for seeded and newly authored criterion codes: `count_band` uses grounded adverse instances and `ratio_band` in `absolute_difference` mode uses paired female/male counts. The criterion code SHALL NOT select a code-specific runtime plugin. The normal path SHALL NOT issue criterion-level LLM calls or criterion-level fallback calls.

#### Scenario: Complete combined extraction
- **WHEN** GAD evaluates an SLM with valid frozen context and resolved form snapshot
- **THEN** the system SHALL make one GAD extraction call and receive factual sections for every criterion in the snapshot

#### Scenario: GAD snapshot adds or reorders supported criterion codes
- **WHEN** a GAD snapshot adds, removes, or reorders criteria using a supported count or paired-count measurement shape
- **THEN** the one-call envelope SHALL be generated in snapshot order and score every included criterion from its configured strategy

#### Scenario: GAD remains an outer-parallel agent
- **WHEN** the supervisor dispatches Layer 3 agents
- **THEN** GAD SHALL run as one agent future without spawning nested criterion-level parallel or sequential LLM execution

### Requirement: Final GAD scores remain deterministic and criterion-specific
The system SHALL validate all combined extraction sections before scoring any criterion and SHALL score each GAD criterion through the registered deterministic GAD scorers configured in the pre-resolved GAD form snapshot. Criteria requiring adverse-instance lists (such as GAD-01, GAD-03, GAD-04, GAD-05) SHALL be scored using the `count_band` strategy in `maximum_count` mode so fewer grounded adverse instances score higher; criteria requiring paired counts (such as female/male counts in GAD-02) SHALL be scored using the `ratio_band` strategy. Revision 1 SHALL preserve GAD-01 maximum-count thresholds 0/1/3 for scores 4/3/2 and GAD-03/04/05 thresholds 0/2/5, with counts above the score-2 threshold scoring 1. The LLM extraction response SHALL NOT contain or be the authority for final numeric GAD scores, and scoring SHALL NOT perform worker-side database queries for rubric definitions.

#### Scenario: Valid facts are scored through the registry
- **WHEN** the combined extraction returns valid facts for all GAD criteria in the snapshot
- **THEN** the system SHALL apply the corresponding deterministic strategy scorer to each criterion defined in the GAD form snapshot and return the standard GAD result shape

#### Scenario: Identical accepted facts produce identical scores
- **WHEN** the registry receives identical validated facts and the same form snapshot revision
- **THEN** it SHALL produce identical final scores for all GAD criteria

### Requirement: Combined extraction failures are bounded and honest
GAD prompt budgets SHALL be derived from serialized prompt contents and form guidance constraints. Repair SHALL be one whole-envelope attempt over frozen context with bounded validator category/path and no rejected-output echo; no criterion-level fallback or broad `except Exception` fallback is allowed.

The system SHALL use at most one GAD-specific whole-envelope repair attempt for malformed, duplicate, missing, or field-invalid combined output. The repair SHALL use the same frozen context and SHALL request the complete fact-only envelope without numeric scores. If required criterion sections remain invalid after bounded repair, the system SHALL record one GAD failure with known runtime metadata when available and SHALL use normal partial-evaluation synthesis behavior without issuing criterion-level fallback calls or catching broad unhandled exceptions.

#### Scenario: Oversized envelope
- **WHEN** the serialized prompt exceeds the configured budget
- **THEN** packing and repair remain bounded and the agent does not issue extra criterion calls

#### Scenario: Repairable malformed response
- **WHEN** the combined GAD response is malformed but the bounded repair response is valid for all criteria
- **THEN** the system SHALL score the repaired facts through the deterministic registry

#### Scenario: Unrecoverable incomplete response
- **WHEN** the combined GAD response remains missing or invalid for one or more required criteria after bounded repair
- **THEN** the system SHALL record one failed GAD agent result without broad unhandled exception swallowing and SHALL NOT start criterion-level fallback calls

### Requirement: GAD frozen context and schema versions are stable
Duplicate frozen chunk IDs SHALL fail closed. The extraction envelope identity and scoring thresholds SHALL be bound strictly to the evaluation's pre-resolved GAD form snapshot revision, payload hash, and adapter version.

#### Scenario: Duplicate context IDs
- **WHEN** frozen GAD context contains duplicate chunk identifiers
- **THEN** extraction fails closed before evidence grounding or scoring

#### Scenario: Snapshot envelope binding
- **WHEN** GAD extraction executes
- **THEN** the extraction schema and registry scoring use the exact bound form snapshot revision and hash
