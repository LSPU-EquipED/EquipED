# evaluations Specification

## Purpose
Define the evaluation job contract for the current phase, including Layer 3 execution, persistence of evaluation outputs, and honest stopping before Layer 4 report generation.

## Requirements

### Requirement: Evaluation jobs progress into Layer 3
The system SHALL support evaluation job submission, pre-agent processing, and execution of the Layer 3 multi-agent evaluation boundary. Layer 3 agent execution SHALL run agents in parallel using a thread pool, with each agent assigned a distinct LLM model to avoid rate-limit contention.

#### Scenario: Evaluation job is accepted and begins processing
- **WHEN** an authenticated user submits a new evaluation request for a document they own
- **THEN** the system SHALL create an evaluation job in `SUBMITTED` state and continue into the pre-agent processing stages

#### Scenario: Layer 3 execution starts after pre-agent processing
- **WHEN** an evaluation job completes the pre-agent stages
- **THEN** the system SHALL enter Layer 3 multi-agent evaluation, run all agents in parallel via `ThreadPoolExecutor`, and record progress without claiming the job is complete

#### Scenario: Precomputed context is shared across parallel agents
- **WHEN** Layer 3 parallel execution begins
- **THEN** the supervisor SHALL pre-compute rubric and reference context sequentially before dispatching agents in parallel
- **AND** all agents SHALL receive the same read-only precomputed context

#### Scenario: Parallel agent execution completes
- **WHEN** all parallel agent futures complete (success or failure)
- **THEN** the system SHALL collect all results and proceed to persistence
- **AND** a single agent failure SHALL NOT prevent other agents from completing

#### Scenario: Inter-agent pacing delays are removed
- **WHEN** agents run in parallel with distinct models
- **THEN** the system SHALL NOT apply inter-agent sleep delays between agent executions
- **AND** pacing delays SHALL only be used as a fallback when all agents share the same model

### Requirement: Evaluation outputs are persisted before stopping
The system SHALL persist Layer 3 outputs for the evaluation job after all parallel agents complete, before the workflow stops at the unimplemented Layer 4 boundary.

#### Scenario: Layer 3 outputs are stored after parallel completion
- **WHEN** all parallel agent futures complete
- **THEN** the system SHALL persist the outputs through the evaluation data persistence contract sequentially

#### Scenario: Persisted outputs remain tied to the job
- **WHEN** evaluation outputs are saved
- **THEN** the system SHALL associate them with the owning evaluation job and document owner

### Requirement: Layer 4 synthesis and monitoring matrix updates
The system SHALL run Layer 4 synthesis after persisting Layer 3 outputs, including weighted score aggregation, monitoring matrix updates, and COMPLETED/FAILED job transitions.

**Domain weights for synthesized scoring:**
- SME (Subject Matter Expert): 35%
- Coordinator (Program Coordinator): 30%
- GAD (Gender & Development): 20%
- ITSO (IT Security Officer): 15%

**Normalization:** If an agent fails or is missing, the weights of successful agents SHALL be normalized to sum to 100%. If all agents fail, the synthesized score SHALL be 0.0 and the result SHALL be marked as partial.

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

#### Scenario: Synthesis completes and job finishes
- **WHEN** synthesis and matrix updates succeed
- **THEN** the system SHALL transition the job to `COMPLETED` (or `FAILED` if synthesis is partial)

### Requirement: Evaluation polling is limited to the owning user
The system SHALL only expose evaluation status for jobs owned by the authenticated user who is polling them.

#### Scenario: User polls their own job
- **WHEN** an authenticated user requests the status of an evaluation job they created
- **THEN** the system SHALL return that job's current state and progress information

#### Scenario: User attempts to poll another user's job
- **WHEN** an authenticated user requests the status of an evaluation job owned by a different user
- **THEN** the system SHALL deny access and SHALL not disclose the other job's status

### Requirement: Evaluation lifecycle status sequence
Evaluation jobs SHALL progress through the following status sequence: `SUBMITTED` → `PREPROCESSING` → `EVALUATING` → `SYNTHESIZING` → `COMPLETED`. Jobs that encounter errors SHALL transition to `FAILED` from any non-terminal status. The `EMBEDDING` status SHALL NOT be used. During the `EVALUATING` phase, the system SHALL emit a heartbeat before dispatching parallel agents and after all agents complete.

#### Scenario: Job progresses through lifecycle with parallel execution
- **WHEN** an evaluation job is submitted and accepted
- **THEN** the system SHALL transition through `SUBMITTED` → `PREPROCESSING` → `EVALUATING` (parallel agents) → `SYNTHESIZING` → `COMPLETED` (or `FAILED` on error)

#### Scenario: Heartbeat during parallel execution
- **WHEN** the system enters the `EVALUATING` phase with parallel agents
- **THEN** a heartbeat SHALL be emitted before dispatching agents to the thread pool
- **AND** a heartbeat SHALL be emitted after all agent futures complete

#### Scenario: Job fails during processing
- **WHEN** an error occurs during any non-terminal stage
- **THEN** the system SHALL transition the job to `FAILED` and record the error message

### Requirement: SLM documents are direct evaluation input
Student Learning Materials (SLMs) SHALL be treated as direct evaluation input and SHALL NOT be embedded into the vector store. Only reference documents (syllabus, curriculum) and rubric documents SHALL be embedded.

#### Scenario: SLM document is uploaded
- **WHEN** a document with `source_type == "slm"` is uploaded
- **THEN** the system SHALL ingest and chunk the document but SHALL NOT embed it into ChromaDB

#### Scenario: SLM document is submitted for evaluation
- **WHEN** an evaluation is submitted with an SLM document
- **THEN** the system SHALL accept the document without requiring `chroma_stored == True`

### Requirement: chroma_stored validation is conditional on document type
The `chroma_stored` readiness gate SHALL only apply to documents that require embedding (reference and rubric documents). SLM documents SHALL be exempt from the `chroma_stored` check during evaluation submission validation.

#### Scenario: Reference document without chroma_stored is rejected
- **WHEN** an evaluation is submitted with a reference document (syllabus or curriculum) that has `chroma_stored == False`
- **THEN** the system SHALL reject the submission with an error

#### Scenario: SLM document without chroma_stored is accepted
- **WHEN** an evaluation is submitted with an SLM document that has `chroma_stored == False`
- **THEN** the system SHALL accept the submission (SLMs do not require embedding)

### Requirement: Evaluations may use shared references
The system SHALL allow a user to submit an evaluation for an SLM document they own while attaching institution-shared syllabus and curriculum references uploaded by an admin. Ownership validation SHALL remain strict for the SLM document and SHALL NOT require the user to own the attached curriculum reference. Syllabus references remain optional and are not required by the program-confirmed curriculum selection flow.

#### Scenario: Faculty submits own SLM with shared references
- **WHEN** an authenticated faculty user submits an evaluation for an SLM document they own and attaches processed syllabus/curriculum references uploaded by an admin
- **THEN** the system SHALL accept the evaluation if the references are processed and embedded

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
