## MODIFIED Requirements

### Requirement: GAD evidence is grounded in frozen evaluation context
GAD SHALL match cited source text and chunk IDs exactly; normalization is permitted only for duplicate detection. Every supplied instance SHALL be validated before applying the cap of ten.

#### Scenario: Near-match citation
- **WHEN** an excerpt differs by case or whitespace from its cited chunk
- **THEN** it is rejected as ungrounded

### Requirement: Combined extraction failures are bounded and honest
GAD prompt budgets SHALL be derived from serialized prompt contents. Repair SHALL be one whole-envelope attempt over frozen context with bounded validator category/path and no rejected-output echo; no criterion-level fallback is allowed.

#### Scenario: Oversized envelope
- **WHEN** the serialized prompt exceeds the configured budget
- **THEN** packing and repair remain bounded and the agent does not issue extra criterion calls

### Requirement: GAD frozen context and schema versions are stable
Duplicate frozen chunk IDs SHALL fail closed. Changes to the extraction envelope SHALL bump the extraction-schema version without changing deterministic registry thresholds.

#### Scenario: Duplicate context IDs
- **WHEN** frozen GAD context contains duplicate chunk identifiers
- **THEN** extraction fails closed before evidence grounding or scoring
