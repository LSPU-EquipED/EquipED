## MODIFIED Requirements

### Requirement: Evaluations may use shared references
The system SHALL allow a user to submit an evaluation for an SLM document they own while attaching institution-shared syllabus and curriculum references uploaded by an admin. Ownership validation SHALL remain strict for the SLM document and SHALL NOT require the user to own the attached curriculum reference. Syllabus references remain optional and are not required by the program-confirmed curriculum selection flow. Curriculum references are required for full curriculum-grounded evaluation, but may be omitted only for an explicit no-curriculum partial evaluation.

#### Scenario: Faculty submits own SLM with shared references
- **WHEN** an authenticated faculty user submits an evaluation for an SLM document they own and attaches processed syllabus/curriculum references uploaded by an admin
- **THEN** the system SHALL accept the evaluation if the references are processed and embedded

#### Scenario: Faculty submits own SLM with shared curriculum
- **WHEN** an authenticated faculty user submits an evaluation for an SLM document they own and attaches a processed curriculum reference uploaded by an admin
- **THEN** the system SHALL accept the evaluation if the curriculum reference is processed and embedded

#### Scenario: Faculty submits own SLM for explicit no-curriculum partial evaluation
- **WHEN** an authenticated faculty user submits an evaluation for an SLM document they own with no curriculum reference and explicit no-curriculum partial intent
- **THEN** the system SHALL accept the evaluation as partial
- **AND** the system SHALL NOT treat the job as a full curriculum-grounded evaluation

#### Scenario: Faculty omits curriculum without partial intent
- **WHEN** an authenticated faculty user submits an evaluation for an SLM document they own with no curriculum reference and no explicit no-curriculum partial intent
- **THEN** the system SHALL reject the submission with a clear validation error

#### Scenario: Faculty cannot evaluate another user's SLM
- **WHEN** an authenticated faculty user submits an evaluation for an SLM document owned by another user
- **THEN** the system SHALL reject the submission even if the attached references are shared

#### Scenario: Shared reference must be processed and embedded
- **WHEN** an evaluation submission attaches a syllabus or curriculum reference that is not processed or lacks required Chroma embeddings
- **THEN** the system SHALL reject the submission with a clear validation error

#### Scenario: Rubric documents are not selectable references
- **WHEN** an evaluation submission attempts to attach a rubric document as a syllabus or curriculum reference
- **THEN** the system SHALL reject the submission because the reference source type does not match the expected type

### Requirement: Layer 4 synthesis and monitoring matrix updates
The system SHALL run Layer 4 synthesis after persisting Layer 3 outputs, including weighted score aggregation, monitoring matrix updates, and COMPLETED/FAILED job transitions.

**Domain weights for synthesized scoring:**
- SME (Subject Matter Expert): 35%
- Coordinator (Program Coordinator): 30%
- GAD (Gender & Development): 20%
- ITSO (IT Security Officer): 15%

**Normalization:** If an agent fails, is skipped, or is missing, the weights of successful agents SHALL be normalized to sum to 100%. If all agents fail, the synthesized score SHALL be 0.0 and the result SHALL be marked as partial. No-curriculum partial evaluations SHALL be marked partial because Coordinator curriculum-grounded review is unavailable, but SHALL complete successfully because the partial mode was explicitly selected.

#### Scenario: Synthesis runs after Layer 3
- **WHEN** Layer 3 persistence succeeds
- **THEN** the system SHALL transition to `SYNTHESIZING`, compute weighted domain scores, and write a `monitoring_matrix` row

#### Scenario: Successful weighted synthesis
- **GIVEN** an evaluation with SME 90, Coordinator 80, GAD 100, ITSO 70
- **WHEN** synthesis runs
- **THEN** the synthesized score SHALL be approximately 86.0 (90×0.35 + 80×0.30 + 100×0.20 + 70×0.15)

#### Scenario: Synthesis with a failed agent
- **GIVEN** an evaluation where GAD failed but SME, Coordinator, and ITSO succeeded
- **WHEN** synthesis runs
- **THEN** the weights for SME (35%), Coordinator (30%), and ITSO (15%) SHALL be normalized to sum to 100%
- **AND** a synthesized score SHALL still be produced based on available data with `is_partial=True`

#### Scenario: Synthesis with no-curriculum partial evaluation
- **GIVEN** a no-curriculum partial evaluation where SME, GAD, and ITSO succeeded and Coordinator was skipped or marked limited
- **WHEN** synthesis runs
- **THEN** the weights for SME (35%), GAD (20%), and ITSO (15%) SHALL be normalized to sum to 100%
- **AND** the synthesized output SHALL be marked partial with a missing-curriculum explanation
- **AND** the evaluation job SHALL transition to `COMPLETED` rather than `FAILED`

#### Scenario: Synthesis completes and job finishes
- **WHEN** synthesis and matrix updates succeed
- **THEN** the system SHALL transition the job to `COMPLETED` for complete results or deliberate no-curriculum partial results
- **AND** the system SHALL transition to `FAILED` for accidental partial results caused by agent execution failures
