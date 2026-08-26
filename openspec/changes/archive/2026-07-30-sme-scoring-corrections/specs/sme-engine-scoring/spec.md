## ADDED Requirements

### Requirement: A-01 normalizes bounded Bloom-taxonomy synonyms
The A-01 extractor SHALL request the canonical category name—not the example
action verb—from `remember`, `understand`, `apply`, `analyze`, `evaluate`, or
`create`. Before scoring, the engine SHALL preserve the existing normalized
canonical-prefix behavior and normalize this bounded set of exact aliases after
trimming and case-folding:

| Canonical level | Accepted values |
| --- | --- |
| `remember` | `list` |
| `understand` | `explain` |
| `analyze` | `compare` |
| `evaluate` | `justify` |

Alias normalization SHALL use exact normalized values, not fuzzy or similarity
matching. Unknown values SHALL retain conservative treatment and SHALL NOT be
promoted to a higher-order level.

#### Scenario: Compare is normalized as analyze
- **WHEN** A-01 factual extraction returns `compare` as a Bloom level
- **THEN** the engine SHALL normalize it to `analyze` before deciding whether
  the task is higher-order

#### Scenario: Canonical level remains unchanged
- **WHEN** A-01 factual extraction returns `evaluate`
- **THEN** the engine SHALL retain `evaluate` without synonym remapping

#### Scenario: Unknown label is not promoted
- **WHEN** A-01 factual extraction returns a value outside the canonical and
  bounded synonym values
- **THEN** the engine SHALL NOT treat it as higher-order solely by similarity

### Requirement: A-04 excludes non-feedback legal and administrative boilerplate
The A-04 extraction prompts SHALL instruct the model not to classify legal
disclaimers, copyright notices, fair-use statements, administrative boilerplate,
or institutional-policy notices as feedback mechanisms, and SHALL request a
minimal quote directly evidencing the feedback mechanism. After feedback-type
normalization and before counting, the deterministic path SHALL apply a
boilerplate guard only to `positive_reinforcement` evidence.

The guard SHALL reject only high-confidence boilerplate phrases: all-rights-
reserved notices, copyright ownership/year notices, fair-use disclaimers,
reproduction/distribution prohibitions, or `under/pursuant to Section ...
RA/Republic Act` notices. An RA citation alone, or generic `section` or
`policy` wording, SHALL NOT cause rejection. Evidence with a qualifying
boilerplate phrase and explicit learner-directed praise SHALL remain eligible.

#### Scenario: Copyright disclaimer is proposed as feedback
- **WHEN** extracted A-04 evidence is a copyright or fair-use disclaimer
- **THEN** the engine SHALL exclude that item from feedback-type counting

#### Scenario: Republic Act notice is proposed as positive reinforcement
- **WHEN** extracted A-04 evidence is an `under/pursuant to Section ...
  RA/Republic Act` notice without learner-directed feedback content
- **THEN** the engine SHALL exclude that item from feedback-type counting

#### Scenario: Legal-themed answer key is preserved
- **WHEN** A-04 evidence is an answer key, rubric, or remediation guidance that
  discusses a law or policy without a qualifying boilerplate phrase
- **THEN** the engine SHALL not reject it solely because of that legal topic

#### Scenario: Genuine learner feedback is preserved
- **WHEN** A-04 evidence contains learner-directed encouragement, a rubric,
  an answer key, or remediation guidance without high-confidence legal
  boilerplate markers
- **THEN** the engine SHALL continue to evaluate it under the existing A-04
  feedback-type and count-band rules

## MODIFIED Requirements

### Requirement: SME engine limitations remain visible for future remediation
The scoring contract SHALL preserve the following known limitations without
treating them as accepted quality outcomes:

- `A-01` normalizes only the four observed non-canonical Bloom aliases. Other
  non-canonical labels remain conservatively unrecognized until a reviewed
  example justifies a bounded mapping.
- `A-04` rejects only high-confidence boilerplate proposed as
  `positive_reinforcement`. Unrecognized boilerplate wording remains eligible
  for future review rather than being broadly filtered.
- `A-05` currently counts both broad intended learning outcomes and specific
  targets when they are not exact duplicates; the intended hierarchy rule is
  unresolved and requires an institutional-policy decision.

#### Scenario: Known scoring limitation is revisited
- **WHEN** future work changes a bounded A-01/A-04 correction or the A-05
  objective hierarchy
- **THEN** it SHALL establish and document the institutional counting rule with
  representative evidence before changing the current behavior
