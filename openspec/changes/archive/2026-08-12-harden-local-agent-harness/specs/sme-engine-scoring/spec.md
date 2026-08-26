## MODIFIED Requirements

### Requirement: SME fact extraction is deterministic and basketed
SME SHALL use strict non-coercing agent-local schemas for grouped and per-criterion responses. Missing, wrong, duplicate, unknown, or invalid-reference fields SHALL invalidate an atomic basket; valid empty arrays remain valid findings. Existing bounded per-criterion fallback SHALL be used without an SME repair call, and failed criteria SHALL fail honestly rather than receive invented scores.

#### Scenario: Empty object is rejected
- **WHEN** a basket returns `{}`
- **THEN** it is schema-invalid and uses the existing bounded fallback rather than becoming a low score

### Requirement: Engine extraction uses bounded, representative document slices
SME SHALL consume canonical clean source text prepared before dispatch and SHALL NOT reopen PDFs or duplicate full source persistence.

#### Scenario: Canonical source dispatch
- **WHEN** SME evaluates a document
- **THEN** it scores from the shared canonical text and records bounded telemetry only

### Requirement: SME completion and fixed budgets are honest
An SME basket with provider `finish_reason=length` SHALL be invalid. Contractually fixed source slices and completion caps SHALL NOT be silently trimmed. Valid empty arrays SHALL remain valid findings.

#### Scenario: Truncated basket
- **WHEN** the provider finishes a basket with reason `length`
- **THEN** that basket fails and follows the bounded fallback path without scoring truncated output
