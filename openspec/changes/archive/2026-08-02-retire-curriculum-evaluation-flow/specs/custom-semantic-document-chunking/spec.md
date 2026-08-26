## ADDED Requirements

### Requirement: Retired curriculum and rubric PDFs are not ingestion targets
The active document ingestion pipeline SHALL NOT process or embed newly uploaded
curriculum or rubric PDF source types. SLM handling, syllabus embedding, and
policy collection handling remain unchanged.

#### Scenario: Retired source reaches ingestion
- **WHEN** a curriculum or rubric PDF source request reaches document validation
- **THEN** the system SHALL reject it before extraction, chunking, or embedding
