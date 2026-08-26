## ADDED Requirements

### Requirement: Metadata detection step in preprocessing
The preprocessing pipeline SHALL include a metadata detection step that runs after text extraction and before embedding. This step SHALL use regex pattern matching to extract `program`, `academic_year`, and `course_code` from the first 2-3 pages of extracted text.

#### Scenario: Metadata detected during preprocessing
- **WHEN** a document is uploaded and text extraction completes
- **THEN** the system SHALL run regex-based metadata detection on the first 2-3 pages of extracted text
- **AND** SHALL persist any detected values to the Document record

#### Scenario: Metadata detection does not block preprocessing
- **WHEN** metadata detection finds no matches or raises an exception
- **THEN** the system SHALL continue preprocessing normally without errors
