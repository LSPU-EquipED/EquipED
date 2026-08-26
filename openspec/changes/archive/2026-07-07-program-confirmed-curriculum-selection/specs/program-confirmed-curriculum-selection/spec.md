## ADDED Requirements

### Requirement: Evaluation setup requires program confirmation
The system SHALL require a faculty user to confirm or select the academic program before creating a fresh evaluation that uses curriculum grounding.

#### Scenario: Program detected from SLM
- **WHEN** a faculty user opens evaluation setup for a processed SLM with a detected program
- **THEN** the system SHALL preselect that program
- **AND** the faculty user SHALL be able to change the selected program before starting evaluation

#### Scenario: Program not detected from SLM
- **WHEN** a faculty user opens evaluation setup for a processed SLM with no detected program
- **THEN** the system SHALL require the faculty user to select a program before curriculum suggestion is shown

#### Scenario: GE or minor subject does not imply program
- **WHEN** an SLM only identifies a GE/minor course or subject title
- **THEN** the system SHALL NOT infer program from that course or subject alone

### Requirement: Curriculum suggestions are program-driven
The system SHALL suggest CHED curriculum references using the confirmed program. Course code, Sem/AY, and lesson title SHALL be displayed as context but SHALL NOT determine the curriculum. Program matching SHALL normalize values before comparison.

#### Scenario: Matching curriculum exists
- **WHEN** a faculty user confirms program `BSCS` and an embedding-ready curriculum reference exists for `BSCS`
- **THEN** the system SHALL suggest that curriculum for evaluation

#### Scenario: Multiple curricula match program
- **WHEN** multiple embedding-ready curriculum references match the confirmed program
- **THEN** the system SHALL preselect the newest uploaded reference
- **AND** the system SHALL allow the faculty user to choose another matching curriculum

#### Scenario: No curriculum match exists
- **WHEN** no embedding-ready curriculum reference exists for the confirmed program
- **THEN** the system SHALL block evaluation start and explain that the curriculum must be uploaded or rebuilt by an admin

#### Scenario: Unhealthy curriculum is available
- **WHEN** a curriculum reference exists for the confirmed program but is not embedding-ready
- **THEN** the system SHALL show it as unavailable for evaluation and direct the user/admin to rebuild or re-upload it

#### Scenario: Program parameter is empty
- **WHEN** the system requests curriculum suggestions without a selected program
- **THEN** the system SHALL reject the suggestion request with a clear validation error instead of returning all curricula

#### Scenario: Program values differ only by case or whitespace
- **WHEN** the selected program is `bscs` and the curriculum reference stores `BSCS`
- **THEN** the system SHALL treat them as the same program for suggestion purposes

### Requirement: Fresh evaluation submission uses selected curriculum
The system SHALL submit fresh evaluations with the selected curriculum reference. Syllabus selection SHALL NOT be required by this flow.

#### Scenario: Faculty starts evaluation after confirming curriculum
- **WHEN** a faculty user confirms an embedding-ready curriculum for their own SLM
- **THEN** the system SHALL submit the evaluation with `document_id` and `curriculum_id`
- **AND** `syllabus_id` SHALL be omitted or null

#### Scenario: Existing evaluation is reused
- **WHEN** an evaluation already exists for the SLM and is reusable by the current frontend flow
- **THEN** the system MAY skip setup and continue to the existing evaluation status/results view

#### Scenario: Retry after failed evaluation
- **WHEN** a faculty user retries a failed evaluation after clearing the existing evaluation state
- **THEN** the system SHALL return to curriculum setup before creating a fresh evaluation

### Requirement: Curriculum suggestion preserves RAG retrieval
The system SHALL use curriculum suggestion only to select the curriculum document. Evaluation-time RAG retrieval SHALL continue to retrieve relevant chunks from the selected curriculum reference in ChromaDB.

#### Scenario: Selected curriculum scopes retrieval
- **WHEN** evaluation starts with a selected curriculum reference
- **THEN** the evaluation pipeline SHALL use that curriculum reference as the source for reference context retrieval
- **AND** ChromaDB retrieval SHALL still select relevant chunks from that curriculum

### Requirement: Admin curriculum references require program metadata
The system SHALL require program metadata for curriculum reference uploads or management because curriculum suggestion is program-driven. Program values SHALL be stored or compared using normalized program codes.

#### Scenario: Admin uploads curriculum without program
- **WHEN** an admin uploads a curriculum reference without a program value
- **THEN** the system SHALL reject the upload or require the admin to provide a program before the curriculum can be used for suggestion

#### Scenario: Admin uploads curriculum with program
- **WHEN** an admin uploads a curriculum reference with a valid program value
- **THEN** the system SHALL process the document normally and make it eligible for program-based suggestion once embedding-ready
