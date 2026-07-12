# itso-scoring-consistency Specification

## Purpose
Define the deterministic generation, bounded provenance, and local evidence precheck contract for the ITSO agent so that repeated evaluations of the same document produce auditable, consistent, and honest results.

## Requirements

### Requirement: ITSO evaluation uses deterministic generation settings
The system SHALL invoke the ITSO evaluator with an ITSO-specific temperature default of `0.0` and SHALL preserve the requested generation setting with the resulting agent output.

#### Scenario: ITSO evaluation is dispatched
- **WHEN** an evaluation dispatches the ITSO agent
- **THEN** the agent SHALL use the configured ITSO-specific deterministic temperature
- **AND** the result provenance SHALL record the requested temperature and requested model identifier

#### Scenario: Provider serves a fallback model
- **WHEN** the ITSO client falls back to another configured model after a retryable provider failure
- **THEN** the result provenance SHALL record both the requested model and the actual served model
- **AND** the system SHALL NOT represent the fallback result as having been served by the requested model alone

### Requirement: ITSO evidence is frozen and provenance is bounded
The system SHALL build one bounded ITSO evidence/provenance snapshot before agent dispatch and SHALL persist it with the ITSO result without storing raw SLM or prompt text.

#### Scenario: ITSO evidence is prepared
- **WHEN** supervisor precomputation prepares ITSO evaluation context
- **THEN** it SHALL preserve deterministic ordered chunk identifiers, prompt/rubric identifiers or hashes, precheck version, and prompt-budget flags in an immutable snapshot
- **AND** the ITSO execution SHALL use that snapshot rather than rebuilding its evidence independently

#### Scenario: ITSO result is persisted
- **WHEN** an ITSO result is persisted
- **THEN** its provenance SHALL record actual model, fallback/repair indicators, context or prompt trim indicators, and bounded evidence identifiers or hashes
- **AND** it SHALL NOT persist raw prompt text, raw SLM text, full chunk text, credentials, or external request payloads

### Requirement: Local citation and reference prechecks are deterministic and advisory
The system SHALL derive stable local citation/reference precheck signals from already-authorized SLM evidence before ITSO prompt assembly. These signals SHALL inform review but SHALL NOT make plagiarism, legal, or source-validity determinations.

#### Scenario: SLM contains references and citations
- **WHEN** local prechecks find candidate bibliography entries, in-text citation patterns, or DOI patterns
- **THEN** the snapshot SHALL include stable counts and bounded identifiers derived from those patterns
- **AND** the ITSO prompt SHALL treat them as evidence signals rather than external verification

#### Scenario: Local prechecks find insufficient evidence
- **WHEN** local prechecks cannot reliably establish a citation or reference signal
- **THEN** the ITSO output SHALL use an explicit insufficient or unverified evidence status where applicable
- **AND** SHALL NOT assert plagiarism, misconduct, invalid citation, or legal noncompliance solely from the missing signal

### Requirement: ITSO consistency is regression-tested
The system SHALL provide fixture-driven tests and an offline benchmark harness for repeat ITSO evaluation inputs.

#### Scenario: Fixed inputs are evaluated repeatedly with a deterministic client
- **WHEN** the same fixture, rubric version, evidence snapshot, and deterministic fake client are evaluated repeatedly
- **THEN** local prechecks, prompt assembly, provenance, and normalized criterion-score output SHALL remain identical

#### Scenario: Live provider benchmark is run
- **WHEN** maintainers run the documented live-provider repeat benchmark
- **THEN** the benchmark SHALL report criterion/subtotal variation together with actual-model, fallback, repair, and trimming provenance
- **AND** it SHALL not modify production evaluation scores or job status
