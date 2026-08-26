## MODIFIED Requirements

### Requirement: Admin reference library lists syllabus and curriculum documents
The system SHALL provide an admin-only reference library listing for documents with source types `syllabus` and `curriculum`. Rubric documents SHALL NOT be included in this library. Curriculum references SHALL include program metadata to support program-driven suggestion.

#### Scenario: Admin lists references
- **WHEN** an authenticated admin requests the reference library
- **THEN** the system SHALL return syllabus and curriculum documents with metadata, upload date, processing status, and local health indicators

#### Scenario: Rubrics are excluded
- **WHEN** the reference library contains uploaded rubric documents
- **THEN** the system SHALL exclude `rubric_sme`, `rubric_coord`, `rubric_gad`, and `rubric_itso` documents from the reference library response

#### Scenario: Faculty cannot manage the library
- **WHEN** an authenticated faculty user requests the admin reference library endpoint
- **THEN** the system SHALL deny access

#### Scenario: Curriculum without program is not suggestion-ready
- **WHEN** a curriculum reference has no program metadata
- **THEN** the system SHALL treat it as not eligible for program-driven curriculum suggestion until program metadata is provided
