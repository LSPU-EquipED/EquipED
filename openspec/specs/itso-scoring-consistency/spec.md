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

### Requirement: ITSO consistency is regression-tested
ITSO SHALL validate an exact versioned criterion schema with no coercion, duplicates, unknown, empty, or incomplete criteria. It SHALL permit at most one whole-task regeneration from identical frozen context using bounded validator categories/paths.

#### Scenario: Invalid judgment
- **WHEN** output fails the exact schema
- **THEN** one safe regeneration occurs at most, then the result fails honestly without raw-output persistence
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



### Requirement: ITSO evidence is frozen and provenance is bounded
ITSO SHALL prepare one frozen task containing exact active criteria, packed evidence IDs/hashes, precheck and policy mode. Remote requests SHALL receive status-only policy evidence; policy content SHALL be local-only and never fall back externally. Only normalized output and bounded typed metadata SHALL persist; raw responses SHALL NOT persist.

#### Scenario: Policy locality
- **WHEN** policy evidence is disabled or a remote provider is selected
- **THEN** no policy clauses are delivered and local-only mode cannot fall back externally
