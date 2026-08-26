## REMOVED Requirements

### Requirement: Retired curriculum and rubric PDFs are not ingestion targets
**Reason**: Curriculum PDF ingestion is active again for supported programs; rubric PDF ingestion remains retired.

**Migration**: Replaced by `Curriculum PDFs use the active reference ingestion target` below.

## ADDED Requirements

### Requirement: Curriculum PDFs use the active reference ingestion target
The active document ingestion pipeline SHALL process and locally embed newly uploaded curriculum PDFs for BSCS and BSInfoTech using fail-closed extraction, deterministic page-bounded semantic chunking, and the curriculum reference collection. It SHALL continue rejecting rubric PDF source types before extraction.

#### Scenario: Supported curriculum reaches ingestion
- **WHEN** an administrator uploads a supported-program curriculum PDF
- **THEN** the system SHALL extract, program-filter when applicable, chunk, persist, and locally embed the curriculum through the active reference path

#### Scenario: Rubric PDF reaches ingestion
- **WHEN** a rubric PDF source request reaches document validation
- **THEN** the system SHALL reject it before extraction, chunking, or embedding
