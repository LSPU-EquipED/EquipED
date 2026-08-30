## MODIFIED Requirements

### Requirement: Dormant full Coordinator path is authoritative and bounded
Full mode SHALL require a curriculum ID and non-empty authoritative precomputed curriculum, consume it without independent retrieval or fallback, validate exact bounded alignment rows and grounded positive evidence against the pre-resolved Coordinator form snapshot, and use deterministic summary/merge attribution. The Coordinator owns an independent form family and evaluation result contract, and SHALL NOT implicitly treat SME scores as its own or query the database for rubric criteria. Missing runtime curriculum or Coordinator failure SHALL fail a requested full job; only explicit partial intent may complete partial. The Coordinator SHALL remain dormant for ordinary no-curriculum submissions. All generated Coordinator evaluation outputs SHALL remain human-advisory and preserve local data residency.

#### Scenario: Full job lacks curriculum
- **WHEN** full mode is requested without authoritative precomputed curriculum
- **THEN** Coordinator fails, available agents are persisted, synthesis is partial, and the job terminates `FAILED`

#### Scenario: Explicit partial submission
- **WHEN** no-curriculum partial intent is explicit
- **THEN** Coordinator is skipped and the job completes with `COMPLETED_PARTIAL` matrix status

#### Scenario: Coordinator scores using independent form snapshot
- **WHEN** full mode executes with authoritative curriculum
- **THEN** Coordinator evaluates curriculum alignment and rubric criteria defined in its own bound form snapshot without querying the database or inheriting SME scores

### Requirement: Coordinator merge and attribution are exact
Coordinator SHALL validate exact criterion identity and cardinality from its bound form snapshot before attribution. A valid curriculum row with all false indicators SHALL score 1. Coordinator SHALL emit no managed prompt attribution, independent full fallback, or LLM summary, and SHALL NOT perform SME score merging.

#### Scenario: Coordinator merge and attribution are exact
- **WHEN** curriculum alignment rows match the exact criteria defined in the Coordinator form snapshot
- **THEN** the Coordinator evaluates curriculum alignment without merging SME scores or querying external rubrics

#### Scenario: Invalid merge identity
- **WHEN** curriculum alignment rows omit, duplicate, or introduce a criterion not in the Coordinator form snapshot
- **THEN** Coordinator fails closed before scoring

### Requirement: Coordinator objective extraction and claim grounding
Every extracted objective SHALL be bounded, pre-trimmed, duplicate-normalization-unique, and an exact codepoint substring of the frozen SLM document text before curriculum scoring. Duplicate JSON keys and paraphrased/non-substring objectives SHALL fail closed. Structurally valid positive curriculum alignment claims lacking an exact nonempty substring match in authoritative curriculum text SHALL be normalized to false with empty evidence (demotion contract) without LLM retries or full fallbacks. Structural, type, identity, or cardinality violations SHALL NOT be normalized and SHALL fail closed.

#### Scenario: Objective must be exact codepoint substring
- **WHEN** an extracted objective is paraphrased or is not an exact codepoint substring of the frozen SLM text
- **THEN** objective validation fails closed and Coordinator execution fails

#### Scenario: Positive alignment claim substring demotion
- **WHEN** a positive alignment claim's evidence is not an exact nonempty substring of the authoritative curriculum text
- **THEN** the positive claim is normalized to false with empty evidence, attribution rejection counts increment, and scoring proceeds across exact rows
