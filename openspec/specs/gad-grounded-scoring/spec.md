# gad-grounded-scoring Specification

## Purpose

Define the single-pass grounded extraction contract for the GAD evaluation agent, replacing per-criterion sequential LLM calls with one combined fact-only extraction call while preserving deterministic registry scoring, evidence grounding, and honest bounded failure behavior.

## Requirements

### Requirement: GAD uses one normal-path grounded extraction call
The system SHALL execute one normal-path GAD LLM extraction call per evaluation job through a GAD-local fact-only execution pipeline. The call SHALL produce a duplicate-safe ordered list with exactly one named factual section for all five GAD criteria from the frozen, ordered GAD evaluation context. The normal path SHALL NOT issue criterion-level LLM calls or criterion-level fallback calls.

#### Scenario: Complete combined extraction
- **WHEN** GAD evaluates an SLM with valid frozen context
- **THEN** the system SHALL make one GAD extraction call and receive factual sections for every GAD criterion

#### Scenario: GAD remains an outer-parallel agent
- **WHEN** the supervisor dispatches Layer 3 agents
- **THEN** GAD SHALL run as one agent future without spawning nested criterion-level parallel or sequential LLM execution

### Requirement: Final GAD scores remain deterministic and criterion-specific
The system SHALL validate all combined extraction sections before scoring any criterion and SHALL score each GAD criterion through the existing deterministic GAD registry. GAD-01/03/04/05 SHALL supply explicit instance lists, exact excerpts, candidate chunk identifiers, and summaries; GAD-02 SHALL supply female/male counts and a summary. The LLM extraction response SHALL NOT contain or be the authority for final numeric GAD scores.

#### Scenario: Valid facts are scored through the registry
- **WHEN** the combined extraction returns valid facts for all GAD criteria
- **THEN** the system SHALL apply the corresponding deterministic registry scorer to each criterion and return the standard GAD result shape

#### Scenario: Identical accepted facts produce identical scores
- **WHEN** the registry receives identical validated facts and the same registry version
- **THEN** it SHALL produce identical final scores for all GAD criteria

### Requirement: GAD evidence is grounded in frozen evaluation context
The system SHALL validate GAD-01/03/04/05 candidate excerpts and references against the ordered chunk identifiers in the frozen GAD context before scoring. Unknown identifiers, malformed references, duplicate normalized excerpts, and excerpts absent from their cited chunk SHALL NOT be accepted as grounded evidence. GAD-02 remains count-based in this change.

#### Scenario: Unknown evidence reference is rejected
- **WHEN** a combined extraction cites a chunk identifier outside the frozen GAD context
- **THEN** the system SHALL reject that reference and SHALL NOT use it as scoring evidence

#### Scenario: No evidence is not treated as automatic noncompliance
- **WHEN** a criterion has no accepted grounded evidence
- **THEN** the system SHALL apply the existing criterion-specific missing-evidence rule without asserting noncompliance solely from absence

#### Scenario: All candidate evidence is rejected
- **WHEN** no GAD-01/03/04/05 candidate excerpt survives grounding validation
- **THEN** the system SHALL retain the existing zero-accepted-instance scoring behavior and record bounded grounding-degradation provenance

### Requirement: Combined extraction failures are bounded and honest
The system SHALL use at most one GAD-specific whole-envelope repair attempt for malformed, duplicate, missing, or field-invalid combined output. The repair SHALL use the same frozen context and SHALL request the complete fact-only envelope without numeric scores. If required criterion sections remain invalid after bounded repair, the system SHALL record one GAD failure with known runtime metadata when available and SHALL use normal partial-evaluation synthesis behavior without issuing criterion-level fallback calls.

#### Scenario: Repairable malformed response
- **WHEN** the combined GAD response is malformed but the bounded repair response is valid for all criteria
- **THEN** the system SHALL score the repaired facts through the deterministic registry

#### Scenario: Unrecoverable incomplete response
- **WHEN** the combined GAD response remains missing or invalid for one or more required criteria after bounded repair
- **THEN** the system SHALL record one failed GAD agent result and SHALL NOT start criterion-level fallback calls

### Requirement: GAD single-pass execution retains bounded audit metadata
The system SHALL preserve `temperature=0.0`, actual model attribution, prompt-version identity, repair state, prompt trimming state, extraction-schema version, scoring-registry version, and bounded candidate/accepted/rejected evidence counters for single-pass GAD results. Provenance SHALL NOT contain excerpts, raw prompts, raw responses, or document text.

#### Scenario: Successful grounded extraction is persisted
- **WHEN** GAD successfully completes a combined extraction and deterministic scoring
- **THEN** its persisted result SHALL contain only bounded scalar runtime and grounding indicators needed to audit the result

#### Scenario: Expected extraction failure is persisted
- **WHEN** GAD cannot produce a valid combined envelope after bounded repair
- **THEN** it SHALL persist one failed result with actual elapsed time and known model or prompt metadata when available

### Requirement: Single-pass GAD scoring is benchmarked before rollout
The system SHALL support controlled comparison of current and single-pass GAD behavior using representative SLMs. The comparison SHALL record runtime, criterion coverage, grounded evidence quality, and final deterministic scores for human review.

#### Scenario: Benchmark captures acceptance evidence
- **WHEN** maintainers run the GAD comparison benchmark
- **THEN** the system SHALL report runtime and criterion-level result data sufficient for human review before replacing the current extraction topology
