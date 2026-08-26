## MODIFIED Requirements

### Requirement: Curriculum suggestions are program-driven
The system SHALL suggest CHED curriculum references using the confirmed program. Course code, Sem/AY, and lesson title SHALL be displayed as context but SHALL NOT determine the curriculum. Program matching SHALL normalize values before comparison. If no embedding-ready curriculum exists, the setup flow SHALL present recovery actions instead of becoming a dead end.

#### Scenario: Matching curriculum exists
- **WHEN** a faculty user confirms program `BSCS` and an embedding-ready curriculum reference exists for `BSCS`
- **THEN** the system SHALL suggest that curriculum for evaluation

#### Scenario: Multiple curricula match program
- **WHEN** multiple embedding-ready curriculum references match the confirmed program
- **THEN** the system SHALL preselect the newest uploaded reference
- **AND** the system SHALL allow the faculty user to choose another matching curriculum

#### Scenario: No curriculum match exists
- **WHEN** no embedding-ready curriculum reference exists for the confirmed program
- **THEN** the system SHALL explain that no ready curriculum is available for the selected program
- **AND** the system SHALL offer actions to upload or rebuild curriculum, change program, or continue with a no-curriculum partial evaluation

#### Scenario: Unhealthy curriculum is available
- **WHEN** a curriculum reference exists for the confirmed program but is not embedding-ready
- **THEN** the system SHALL show it as unavailable for full evaluation and direct the user/admin to rebuild or re-upload it
- **AND** the system SHALL still allow the user to choose a no-curriculum partial evaluation if they accept the degraded result

#### Scenario: Program parameter is empty
- **WHEN** the system requests curriculum suggestions without a selected program
- **THEN** the system SHALL reject the suggestion request with a clear validation error instead of returning all curricula

#### Scenario: Program values differ only by case or whitespace
- **WHEN** the selected program is `bscs` and the curriculum reference stores `BSCS`
- **THEN** the system SHALL treat them as the same program for suggestion purposes

### Requirement: Fresh evaluation submission uses selected curriculum
The system SHALL submit fresh full evaluations with the selected curriculum reference. Syllabus selection SHALL NOT be required by this flow. When no ready curriculum exists and the user explicitly chooses the degraded path, the system SHALL submit a no-curriculum partial evaluation instead of a full curriculum-grounded evaluation.

#### Scenario: Faculty starts evaluation after confirming curriculum
- **WHEN** a faculty user confirms an embedding-ready curriculum for their own SLM
- **THEN** the system SHALL submit the evaluation with `document_id` and `curriculum_id`
- **AND** `syllabus_id` SHALL be omitted or null

#### Scenario: Faculty starts partial evaluation without curriculum
- **WHEN** a faculty user confirms that no ready curriculum is available and chooses to continue partial
- **THEN** the system SHALL submit the evaluation with `document_id`, no `curriculum_id`, and explicit no-curriculum partial intent
- **AND** the UI SHALL preserve the selected program context for user understanding when available

#### Scenario: Existing evaluation is reused
- **WHEN** an evaluation already exists for the SLM and is reusable by the current frontend flow
- **THEN** the system MAY skip setup and continue to the existing evaluation status/results view

#### Scenario: Retry after failed evaluation
- **WHEN** a faculty user retries a failed evaluation after clearing the existing evaluation state
- **THEN** the system SHALL return to curriculum setup before creating a fresh evaluation
