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

### Requirement: Evaluation lifecycle status sequence
Evaluation jobs SHALL use CAS/token transitions and heartbeat-aware recovery; each logical LLM request SHALL use the transport's absolute monotonic request deadline, and `EMBEDDING` SHALL NOT be used.

#### Scenario: Stale worker recovery
- **WHEN** a non-terminal heartbeat is stale
- **THEN** recovery claims or fails the job only through an ownership-safe CAS transition and drains the next FIFO job
### Requirement: Evaluation polling is limited to the owning user
The system SHALL only expose evaluation status for jobs owned by the authenticated user who is polling them.

#### Scenario: User polls their own job
- **WHEN** an authenticated user requests the status of an evaluation job they created
- **THEN** the system SHALL return that job's current state and progress information

#### Scenario: User attempts to poll another user's job
- **WHEN** an authenticated user requests the status of an evaluation job owned by a different user
- **THEN** the system SHALL deny access and SHALL not disclose the other job's status

#### Scenario: Accepted evaluation appears in the evaluation interfaces
- **WHEN** the backend accepts a new evaluation job
- **THEN** the client SHALL immediately display the accepted job in the document evaluation interface
- **AND** SHALL refresh the authenticated user's Evaluations dashboard
- **AND** the dashboard SHALL poll while it contains non-terminal jobs so completion or failure is shown without a manual page refresh

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
Student Learning Materials (SLMs) SHALL be treated as direct evaluation input and SHALL NOT be embedded into the vector store. Syllabus, curriculum, rubric, and policy documents MAY be embedded into source-appropriate local vector collections. Policy embeddings SHALL be used only for internal ITSO evidence retrieval and SHALL NOT make policies faculty-visible references.

#### Scenario: SLM document is uploaded
- **WHEN** a document with `source_type == "slm"` is uploaded
- **THEN** the system SHALL ingest and chunk the document but SHALL NOT embed it into ChromaDB

#### Scenario: Policy document is embedded for ITSO evidence
- **WHEN** an authenticated admin uploads a policy document with a recognized policy area
- **THEN** the system SHALL chunk and embed it into the dedicated local policy collection
- **AND** SHALL NOT expose the policy as a faculty-selectable evaluation reference

#### Scenario: SLM document is submitted for evaluation
- **WHEN** an evaluation is submitted with an SLM document
- **THEN** the system SHALL accept the document without requiring `chroma_stored == True`

### Requirement: chroma_stored validation is conditional on document type
The `chroma_stored` readiness gate SHALL apply to every document type that requires embedding, including syllabus, curriculum, rubric, and policy documents. SLM documents SHALL be exempt from the `chroma_stored` check during evaluation submission validation.

#### Scenario: Embedding-required document without chroma_stored is unavailable
- **WHEN** a syllabus, curriculum, rubric, or policy document has `chroma_stored == False`
- **THEN** the system SHALL treat that document as unavailable for its source-appropriate retrieval path

#### Scenario: SLM document without chroma_stored is accepted
- **WHEN** an evaluation is submitted with an SLM document that has `chroma_stored == False`
- **THEN** the system SHALL accept the submission (SLMs do not require embedding)

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

### Requirement: Evaluation results retain agent runtime provenance
The system SHALL retain bounded per-agent runtime provenance needed to explain an evaluation result without exposing sensitive evaluation input.

#### Scenario: Agent completes after a runtime variation
- **WHEN** an agent completes using a fallback model, JSON repair, or trimmed evaluation context
- **THEN** the persisted agent result SHALL identify the actual served model and applicable runtime indicators
- **AND** authorized result consumers SHALL be able to distinguish this provenance from raw evaluation content

#### Scenario: Historical result lacks provenance
- **WHEN** an authorized user retrieves an evaluation created before runtime provenance was available
- **THEN** the system SHALL continue to return the historical result successfully
- **AND** SHALL represent unavailable provenance as absent rather than inventing it

### Requirement: New evaluations require explicit confirmed curriculum intent
The system SHALL require an explicit confirmed canonical program write value (`BSCS` or `BSInfoTech`) and one of two non-conflicting intents: full intent with a matching ready curriculum ID and explicit `partial_without_curriculum=false`, or partial intent with no curriculum ID and explicit `partial_without_curriculum=true`. `BSIT` SHALL remain a read alias only and SHALL be rejected on evaluation writes. It SHALL reject missing or conflicting combinations without creating a job. The target lookup SHALL validate missing/foreign/non-SLM ownership with the same masked response before program and curriculum validation. Full curriculum validation SHALL use the documents-owned curriculum-readiness service rather than SQL flags alone.

#### Scenario: Full request is valid
- **WHEN** faculty submits their processed SLM with confirmed BSCS or BSInfoTech program, a ready curriculum for the same program, and partial intent disabled
- **THEN** the system SHALL create a full evaluation linked to that curriculum

#### Scenario: Partial request is valid
- **WHEN** faculty submits their processed SLM with confirmed program, no curriculum ID, and explicit partial intent
- **THEN** the system SHALL create a no-curriculum partial evaluation

#### Scenario: Request combines curriculum and partial intent
- **WHEN** a request includes a curriculum ID and sets partial intent true
- **THEN** the system SHALL reject the conflicting request without creating an evaluation

#### Scenario: Partial flag is omitted
- **WHEN** a caller omits `partial_without_curriculum`
- **THEN** the system SHALL reject the request rather than infer intent

#### Scenario: Legacy program alias is submitted
- **WHEN** a caller submits `BSIT` as confirmed program on a new evaluation
- **THEN** the system SHALL reject the write and require `BSInfoTech`

#### Scenario: Curriculum program mismatches confirmed program
- **WHEN** a full request selects a curriculum whose canonical program differs from the confirmed program
- **THEN** the system SHALL reject the request with a clear validation error

#### Scenario: Curriculum is not ready
- **WHEN** a full request selects a curriculum that is failed, unprocessed, missing chunks, or missing required local vectors
- **THEN** the system SHALL reject the request without creating an evaluation

#### Scenario: Curriculum lacks administrator provenance
- **WHEN** a full request selects a legacy curriculum row not uploaded by an administrator
- **THEN** the system SHALL reject the request without creating an evaluation

### Requirement: Full intent executes Coordinator honestly
A full-intent evaluation SHALL schedule Coordinator with authoritative curriculum text loaded before worker dispatch, SHALL retain full synthesis weights only when required outputs succeed, and SHALL terminate `FAILED` rather than automatically degrade to partial if curriculum or Coordinator becomes unavailable. A partial-intent evaluation SHALL exclude Coordinator before dispatch and SHALL complete as `COMPLETED_PARTIAL` only when every scheduled partial agent succeeds.

#### Scenario: Full evaluation succeeds
- **WHEN** authoritative curriculum text is available and SME, GAD, ITSO, and Coordinator succeed
- **THEN** deterministic synthesis SHALL produce a full completed monitoring matrix with Coordinator attribution

#### Scenario: Curriculum disappears after full submission
- **WHEN** a full-intent job reaches execution without authoritative curriculum text
- **THEN** the system SHALL preserve full intent, synthesize available outputs as applicable, and terminate the job `FAILED`

#### Scenario: Coordinator fails
- **WHEN** a requested full evaluation does not produce a successful Coordinator result
- **THEN** the system SHALL terminate `FAILED` and SHALL NOT relabel the job as partial

#### Scenario: Partial evaluation succeeds
- **WHEN** an explicit partial job's SME, GAD, and ITSO agents all succeed
- **THEN** the job SHALL complete with a `COMPLETED_PARTIAL` matrix and Coordinator SHALL remain excluded

#### Scenario: Partial evaluation agent fails
- **WHEN** an explicit partial job lacks a successful SME, GAD, or ITSO result
- **THEN** the job and matrix SHALL terminate `FAILED` while preserving partial intent


### Requirement: Layer 4 synthesis and monitoring matrix updates
The system SHALL run deterministic Layer 4 synthesis as the terminal automated output. Explicit no-curriculum partial jobs SHALL complete honestly as `COMPLETED` with `COMPLETED_PARTIAL`; requested full jobs with missing curriculum or Coordinator failure SHALL terminate `FAILED` after available outputs are synthesized.

#### Scenario: Terminal synthesis
- **WHEN** Layer 3 persistence finishes
- **THEN** deterministic synthesis writes the matrix and no further automated layer runs
