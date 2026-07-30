# sme-engine-scoring Specification

## Purpose
Defines the established deterministic scoring engine used by the Subject Matter Expert agent.

## Requirements

### Requirement: SME uses deterministic engine scoring as its primary path
The Subject Matter Expert SHALL evaluate its registered rubric criteria through the deterministic engine-scoring path rather than a generic model-assigned final-score path. The engine SHALL produce the standard structured agent result used by synthesis and persistence.

The registered criteria SHALL be `OP-01` through `OP-05` and `A-01` through `A-05`. The engine SHALL read clean source-document text rather than joined overlapping database chunks when constructing its scoring input.

#### Scenario: SME evaluates an SLM
- **WHEN** the SME is dispatched for an evaluation
- **THEN** it SHALL extract structured facts and compute every registered criterion score through the engine-scoring registry

#### Scenario: Engine result is persisted
- **WHEN** the SME engine completes successfully
- **THEN** it SHALL return the same structured agent-result contract used by the other evaluation agents

### Requirement: SME fact extraction is deterministic and basketed
The SME engine SHALL request factual extraction at temperature `0.0` before code-owned scoring. It SHALL use the following six independently executable baskets:

| Basket | Criteria | Purpose |
| --- | --- | --- |
| A1 | `A-02`, `A-05` | objectives and assessment evidence |
| A2 | `A-01`, `OP-02`, `OP-03` | task evidence |
| A3 | `A-03` | progress-monitoring evidence |
| A4 | `OP-05` | enhancement-activity evidence |
| B1 | `OP-01`, `A-04` | topic coherence and feedback evidence |
| B2 | `OP-04` | section-consistency evidence |

`A-03`, `OP-05`, and `OP-04` SHALL remain single-purpose baskets unless a new validation establishes that grouped extraction preserves their evidence. They previously returned empty facts when treated as secondary categories in larger prompts.

#### Scenario: A basket fails independently
- **WHEN** one basket fails to return usable facts
- **THEN** the system SHALL preserve facts returned by other baskets and attempt the missing basket's criteria through the bounded per-criterion fallback path

#### Scenario: All extraction for a criterion fails
- **WHEN** both the grouped basket and per-criterion fallback fail for a registered criterion
- **THEN** the SME execution SHALL fail honestly rather than emit an invented score for that criterion

### Requirement: Coverage criteria use defined ratio bands
The engine SHALL score `OP-01`, `OP-03`, `OP-04`, `A-01`, and `A-05` using a coverage ratio. Standard moderate ratio bands SHALL be score `4` at 80 percent or greater, score `3` at 50 percent or greater, score `2` at 20 percent or greater, and score `1` below 20 percent. An empty denominator SHALL score `1`, because the absence of units to measure is a deficiency, except for the documented `OP-01` short-document rule.

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
The engine SHALL score checklist criteria with the following qualifying counts and score bands:

| Criterion | Counted unit | Score 4 | Score 3 | Score 2 | Score 1 |
| --- | --- | --- | --- | --- | --- |
| `OP-02` | interactive instances | 4+ | 2+ | 1+ | 0 |
| `OP-05` | enhancement instances | 3+ | 2+ | 1+ | 0 |
| `A-02` | distinct assessment types | 5+ | 3+ | 2+ | 0-1 |
| `A-03` | monitoring instances | 4+ | 2+ | 1+ | 0 |
| `A-04` | distinct feedback types | 3+ | 2+ | 1+ | 0 |

`A-02` SHALL count breadth of types, while `A-03` SHALL count distinct instances because ongoing monitoring is frequency-sensitive. `A-04` SHALL count feedback types.

#### Scenario: Assessment tool variety is evaluated
- **WHEN** `A-02` has five or more qualifying distinct assessment types
- **THEN** the engine SHALL assign score `4`

#### Scenario: Ongoing monitoring is evaluated
- **WHEN** `A-03` has four or more qualifying monitoring instances
- **THEN** the engine SHALL assign score `4` even when those instances share a monitoring type

### Requirement: Engine scoring accepts only grounded, deduplicated evidence
A criterion SHALL count an item only when it has real, quotable source-document evidence. A bare title or heading SHALL NOT qualify by itself. The engine SHALL deduplicate comparable units by normalized label before counting. For `OP-04`, a section judged clean may qualify without a quote because absence of an issue is the positive signal; a flagged section SHALL include quoted issue evidence.

#### Scenario: Heading has no supporting content
- **WHEN** an extracted item contains only a title or heading without real source content
- **THEN** the engine SHALL exclude it from the relevant count or ratio

#### Scenario: Duplicate task is repeated in extraction facts
- **WHEN** the same task label appears more than once in extracted facts
- **THEN** the engine SHALL count it once

### Requirement: Engine extraction uses bounded, representative document slices
Whole-document sampling SHALL preserve the full document's coverage through six evenly spaced windows within a 9,000-character budget, with the final window anchored at the true document end. Omitted spans SHALL be represented by a gap marker whose meaning is explained to the extraction prompt.

Task-oriented extraction SHALL prefer the earliest strong bottom-section header among Performance Task(s), Learning Tasks, Enrichment/Enhancement Activities, Assessment Task, and Questions for Reflection; when absent, it SHALL use the document tail. The established basket slice assignments are:

| Basket | Slice |
| --- | --- |
| A1 | 4,000-character objectives head plus 7,000-character bottom section |
| A2, A3, A4 | 9,000-character bottom-section slice |
| B1, B2 | 9,000-character six-window whole-document sample |

#### Scenario: Oversized document is sampled
- **WHEN** a document exceeds the whole-document sampling budget
- **THEN** the engine SHALL use evenly spaced windows and retain the document's true final window

#### Scenario: Task header exists near the document bottom
- **WHEN** a recognized task-section header occurs near the bottom of an SLM
- **THEN** the task-oriented basket SHALL begin its slice at the earliest such header rather than using vocabulary-only markers from lecture content

### Requirement: A-01 normalizes bounded Bloom-taxonomy synonyms
The A-01 extractor SHALL request the canonical category name—not the example action verb—from `remember`, `understand`, `apply`, `analyze`, `evaluate`, or `create`. Before scoring, the engine SHALL preserve the existing normalized canonical-prefix behavior and normalize this bounded set of exact aliases after trimming and case-folding:

| Canonical level | Accepted values |
| --- | --- |
| `remember` | `list` |
| `understand` | `explain` |
| `analyze` | `compare` |
| `evaluate` | `justify` |

Alias normalization SHALL use exact normalized values, not fuzzy or similarity matching. Unknown values SHALL retain conservative treatment and SHALL NOT be promoted to a higher-order level.

#### Scenario: Compare is normalized as analyze
- **WHEN** A-01 factual extraction returns `compare` as a Bloom level
- **THEN** the engine SHALL normalize it to `analyze` before deciding whether the task is higher-order

#### Scenario: Canonical level remains unchanged
- **WHEN** A-01 factual extraction returns `evaluate`
- **THEN** the engine SHALL retain `evaluate` without synonym remapping

#### Scenario: Unknown label is not promoted
- **WHEN** A-01 factual extraction returns a value outside the canonical and bounded synonym values
- **THEN** the engine SHALL NOT treat it as higher-order solely by similarity

### Requirement: A-04 excludes non-feedback legal and administrative boilerplate
The A-04 extraction prompts SHALL instruct the model not to classify legal disclaimers, copyright notices, fair-use statements, administrative boilerplate, or institutional-policy notices as feedback mechanisms, and SHALL request a minimal quote directly evidencing the feedback mechanism. After feedback-type normalization and before counting, the deterministic path SHALL apply a boilerplate guard only to `positive_reinforcement` evidence.

The guard SHALL reject only high-confidence boilerplate phrases: all-rights-reserved notices, copyright ownership/year notices, fair-use disclaimers, reproduction/distribution prohibitions, or `under/pursuant to Section ... RA/Republic Act` notices. An RA citation alone, or generic `section` or `policy` wording, SHALL NOT cause rejection. Evidence with a qualifying boilerplate phrase and explicit learner-directed praise SHALL remain eligible.

#### Scenario: Copyright disclaimer is proposed as feedback
- **WHEN** extracted A-04 evidence is a copyright or fair-use disclaimer
- **THEN** the engine SHALL exclude that item from feedback-type counting

#### Scenario: Republic Act notice is proposed as positive reinforcement
- **WHEN** extracted A-04 evidence is an `under/pursuant to Section ... RA/Republic Act` notice without learner-directed feedback content
- **THEN** the engine SHALL exclude that item from feedback-type counting

#### Scenario: Legal-themed answer key is preserved
- **WHEN** A-04 evidence is an answer key, rubric, or remediation guidance that discusses a law or policy without a qualifying boilerplate phrase
- **THEN** the engine SHALL not reject it solely because of that legal topic

#### Scenario: Genuine learner feedback is preserved
- **WHEN** A-04 evidence contains learner-directed encouragement, a rubric, an answer key, or remediation guidance without high-confidence legal boilerplate markers
- **THEN** the engine SHALL continue to evaluate it under the existing A-04 feedback-type and count-band rules

### Requirement: SME engine limitations remain visible for future remediation
The scoring contract SHALL preserve the following known limitations without treating them as accepted quality outcomes:

- `A-01` normalizes only the four observed non-canonical Bloom aliases. Other non-canonical labels remain conservatively unrecognized until a reviewed example justifies a bounded mapping.
- `A-04` rejects only high-confidence boilerplate proposed as `positive_reinforcement`. Unrecognized boilerplate wording remains eligible for future review rather than being broadly filtered.
- `A-05` currently counts both broad intended learning outcomes and specific targets when they are not exact duplicates; the intended hierarchy rule is unresolved and requires an institutional-policy decision.

#### Scenario: Known scoring limitation is revisited
- **WHEN** future work changes a bounded A-01/A-04 correction or the A-05 objective hierarchy
- **THEN** it SHALL establish and document the institutional counting rule with representative evidence before changing the current behavior
