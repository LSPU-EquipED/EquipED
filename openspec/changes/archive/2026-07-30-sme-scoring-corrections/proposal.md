## Why

The SME engine has two known correctness defects that can distort scores: it
discards semantically valid non-canonical Bloom verbs for A-01, and it can count
legal or administrative boilerplate as A-04 positive reinforcement. Both affect
the stable scoring core and should be corrected before calibration data and a
future SME/Coordinator harness redesign build on them.

## What Changes

- Normalize only the four observed Bloom-taxonomy aliases (`list`, `explain`,
  `compare`, and `justify`) and strengthen extraction prompts to request only
  canonical values.
- Exclude legal, copyright, fair-use, and administrative boilerplate from A-04
  feedback mechanisms through both extraction guidance and deterministic
  evidence filtering.
- Add regression tests for valid Bloom synonyms, legal-boilerplate exclusion,
  and genuine feedback preservation.
- Verify score changes against known examples and a small human-reviewed
  calibration sample.
- Preserve the current A-05 objective-hierarchy behavior; its ILO-versus-target
  counting rule remains an explicit institutional-policy decision.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `sme-engine-scoring`: Corrects A-01 Bloom normalization and A-04 feedback
  evidence qualification while preserving the documented A-05 limitation.

## Impact

- Affected code: SME scoring prompts, deterministic normalization/filtering,
  and scoring tests.
- Affected behavior: A-01 can increase when valid higher-order synonyms were
  previously discarded; A-04 can decrease when legal boilerplate was previously
  misclassified as feedback. Program Coordinator results can change transitively
  because it shares the SME scoring registry.
- APIs, database schema, dependencies, basket membership, and A-05 behavior:
  unchanged.
