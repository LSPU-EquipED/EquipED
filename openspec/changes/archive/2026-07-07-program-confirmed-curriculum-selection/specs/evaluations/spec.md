## MODIFIED Requirements

### Requirement: Evaluations may use shared references
The system SHALL allow a user to submit an evaluation for an SLM document they own while attaching institution-shared curriculum references uploaded by an admin. Ownership validation SHALL remain strict for the SLM document and SHALL NOT require the user to own the attached curriculum reference. Syllabus references remain optional and are not required by the program-confirmed curriculum selection flow.

#### Scenario: Faculty submits own SLM with shared curriculum
- **WHEN** an authenticated faculty user submits an evaluation for an SLM document they own and attaches a processed curriculum reference uploaded by an admin
- **THEN** the system SHALL accept the evaluation if the curriculum reference is processed and embedded

#### Scenario: Faculty cannot evaluate another user's SLM
- **WHEN** an authenticated faculty user submits an evaluation for an SLM document owned by another user
- **THEN** the system SHALL reject the submission even if the attached references are shared

#### Scenario: Shared reference must be processed and embedded
- **WHEN** an evaluation submission attaches a syllabus or curriculum reference that is not processed or lacks required Chroma embeddings
- **THEN** the system SHALL reject the submission with a clear validation error

#### Scenario: Rubric documents are not selectable references
- **WHEN** an evaluation submission attempts to attach a rubric document as a syllabus or curriculum reference
- **THEN** the system SHALL reject the submission because the reference source type does not match the expected type
