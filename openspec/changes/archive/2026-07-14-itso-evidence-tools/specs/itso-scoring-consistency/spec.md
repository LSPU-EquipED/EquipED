## ADDED Requirements

### Requirement: ITSO evidence snapshots and provenance are separate bounded contracts
The system SHALL extend ITSO pre-dispatch preparation with an immutable, attempt-scoped prompt-time policy-evidence snapshot and a separate persisted provenance envelope. The prompt-time snapshot MAY contain bounded policy clauses; persisted provenance SHALL contain only bounded opaque labels/hashes, delivery indicators, outcome states, counts, and versions.

#### Scenario: Evidence tools prepare ITSO context
- **WHEN** supervisor precomputation builds an ITSO evidence snapshot
- **THEN** it SHALL include bounded policy availability/retrieval outcomes and prompt-time policy clauses alongside the existing local precheck signals
- **AND** ITSO execution SHALL use that same immutable snapshot without rebuilding or requerying policy evidence

#### Scenario: Evidence reaches or is trimmed from ITSO prompt
- **WHEN** prompt budgeting retains, trims, or drops a policy evidence section
- **THEN** the persisted provenance SHALL accurately record the section delivery outcome
- **AND** SHALL NOT persist policy clause text

#### Scenario: Evidence tool is disabled or unavailable
- **WHEN** a configured evidence tool is disabled, unhealthy, or unreachable during preparation
- **THEN** the frozen snapshot SHALL preserve an explicit stable unavailable state
- **AND** repeated prompt assembly for that evaluation SHALL retain the same state

### Requirement: ITSO evidence remains advisory by code-owned guardrail
The system SHALL add code-owned ITSO instructions that evidence-tool outcomes are advisory and that absent policy evidence, a Crossref not-found response, or an unavailable external service is never proof of plagiarism, reference invalidity, misconduct, legal violation, or policy noncompliance.

#### Scenario: Evidence tool cannot ground a criterion
- **WHEN** policy evidence is absent or a Crossref outcome is not found or unavailable
- **THEN** the code-owned ITSO guardrail SHALL require an advisory human-review-oriented conclusion
- **AND** SHALL forbid a conclusive negative allegation based on that outcome alone
