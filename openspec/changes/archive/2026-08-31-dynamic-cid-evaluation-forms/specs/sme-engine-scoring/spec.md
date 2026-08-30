## MODIFIED Requirements

### Requirement: SME uses deterministic engine scoring as its primary path
The Subject Matter Expert SHALL evaluate its criteria through snapshot-bound typed scoring using the precomputed in-memory SME form snapshot resolved before worker dispatch. The engine SHALL evaluate criteria according to their configured typed scoring strategies (`ratio_band`, `count_band`, `llm_rubric_guidance`) and SHALL NOT perform runtime database queries to resolve rubric definitions or fallback criteria. The default criteria for Revision 1 SHALL be `OP-01` through `OP-05` and `A-01` through `A-05`, but future revisions SHALL derive criteria and strategies from the bound snapshot. Strategy and mode SHALL select the bounded measurement schema for every seeded or newly authored criterion; the criterion code SHALL NOT select a code-specific runtime plugin.

#### Scenario: SME evaluates an SLM
- **WHEN** the SME is dispatched for an evaluation
- **THEN** it SHALL extract structured facts and compute every criterion score defined in the SME form snapshot without querying the database for rubric rows

#### Scenario: SME evaluates a newly authored criterion code
- **WHEN** an SME snapshot contains a new criterion code configured with a supported guidance, count, or coverage-ratio measurement shape
- **THEN** the engine SHALL derive the bounded extraction contract from the strategy and snapshot metadata and score it without a code deployment

#### Scenario: Engine result is persisted
- **WHEN** the SME engine completes successfully
- **THEN** it SHALL return the structured agent-result contract mapped to the snapshot criterion definitions used by synthesis and persistence

### Requirement: Coverage criteria use defined ratio bands
The engine SHALL score criteria configured with `ratio_band` strategy using a coverage ratio. For Revision 1 default criteria (`OP-01`, `OP-03`, `OP-04`, `A-01`, and `A-05`), standard moderate ratio bands SHALL be score `4` at 80 percent or greater, score `3` at 50 percent or greater, score `2` at 20 percent or greater, and score `1` below 20 percent. Future revisions SHALL read ratio threshold bands from the criterion's `strategy_config`. An empty denominator SHALL score `1`, because the absence of units to measure is a deficiency, except for the documented `OP-01` short-document rule when present.

| Criterion | Numerator | Denominator |
| --- | --- | --- |
| `OP-01` | coherent topic transitions | deduplicated transitions |
| `OP-03` | tasks with clear quotable directions | distinct tasks |
| `OP-04` | internally consistent sections | distinct sections |
| `A-01` | higher-order Bloom tasks with evidence | distinct tasks |
| `A-05` | objectives aligned to a measured assessment | distinct objectives |

#### Scenario: Coverage meets a moderate band
- **WHEN** a coverage criterion has 80 percent or more qualifying units
- **THEN** the engine SHALL assign score `4`

#### Scenario: A measurable unit set is absent
- **WHEN** a coverage criterion other than short-document `OP-01` has no units to measure
- **THEN** the engine SHALL assign score `1`

#### Scenario: OP-01 has a short transition sequence
- **WHEN** `OP-01` has fewer than four transitions
- **THEN** the engine SHALL score by incoherence issue count: zero issues is `4`, one is `3`, two is `2`, and three or more is `1`

### Requirement: Checklist criteria use criterion-specific count bands
The engine SHALL score checklist criteria configured with `count_band` strategy using configured qualifying counts and score bands. For Revision 1 default criteria, the qualifying counts and bands SHALL be:

| Criterion | Counted unit | Score 4 | Score 3 | Score 2 | Score 1 |
| --- | --- | --- | --- | --- | --- |
| `OP-02` | interactive instances | 4+ | 2+ | 1+ | 0 |
| `OP-05` | enhancement instances | 3+ | 2+ | 1+ | 0 |
| `A-02` | distinct assessment types | 5+ | 3+ | 2+ | 0-1 |
| `A-03` | monitoring instances | 4+ | 2+ | 1+ | 0 |
| `A-04` | distinct feedback types | 3+ | 2+ | 1+ | 0 |

Future revisions SHALL read count threshold bands from the criterion's `strategy_config`.

#### Scenario: Assessment tool variety is evaluated
- **WHEN** `A-02` has five or more qualifying distinct assessment types
- **THEN** the engine SHALL assign score `4`

#### Scenario: Ongoing monitoring is evaluated
- **WHEN** `A-03` has four or more qualifying monitoring instances
- **THEN** the engine SHALL assign score `4` even when those instances share a monitoring type
