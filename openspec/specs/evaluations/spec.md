# evaluations Specification

## Purpose
Define the evaluation job contract for the current phase, including Layer 3 execution, persistence of evaluation outputs, and honest stopping before Layer 4 report generation.

## Requirements

### Requirement: Evaluation jobs progress into Layer 3
The system SHALL support targeted single-agent evaluation job submission, pre-agent processing, and execution of the Layer 3 specialist evaluation boundary. Layer 3 agent execution SHALL execute strictly the scheduled `target_agent` (`sme`, `coordinator`, `gad`, or `itso`), dispatching only the chosen agent.

#### Scenario: Evaluation job is accepted and begins processing
- **WHEN** an authenticated user submits a new evaluation request for a document they own specifying a valid `target_agent` in `("sme", "coordinator", "gad", "itso")`
- **THEN** the system SHALL create an evaluation job in `SUBMITTED` state recording `target_agent` and continue into the pre-agent processing stages

#### Scenario: Layer 3 execution starts after pre-agent processing
- **WHEN** an evaluation job completes the pre-agent stages
- **THEN** the system SHALL enter Layer 3 evaluation, execute only the targeted agent specified by `target_agent`, and record progress without claiming the job is complete

#### Scenario: Parallel agent execution completes
- **WHEN** the targeted agent execution completes (success or failure)
- **THEN** the system SHALL collect its result and proceed to persistence

#### Scenario: Inter-agent pacing delays are removed
- **WHEN** an agent executes independently
- **THEN** the system SHALL NOT apply inter-agent sleep delays between agent executions

### Requirement: Precomputed context is shared across parallel agents
The supervisor SHALL resolve the rubric form snapshot strictly for the specified `target_agent` from `rubric_agent_activations` in a single database transaction coordinated with the `EVALUATING` transition and persist it into `evaluation_form_snapshots` with `UNIQUE(evaluation_id, agent_id)`.

#### Scenario: Precomputed context and form snapshots are resolved before dispatch
- **WHEN** Layer 3 execution begins for a single-agent evaluation
- **THEN** the supervisor SHALL resolve and persist the complete immutable form snapshot with verified canonical hash strictly for the `target_agent` on the main thread in a single transaction coordinated with the EVALUATING transition
- **AND** the agent SHALL receive its precomputed context and frozen form snapshot DTO without worker-side database lookups

#### Scenario: Supervisor reuses precreated snapshots without rereading activations
- **WHEN** Layer 3 execution begins for an evaluation with precreated standard snapshots (such as a Model Validation benchmark run)
- **THEN** the supervisor SHALL load and verify the existing `evaluation_form_snapshots` bound to the evaluation job
- **AND** SHALL NOT reread `rubric_agent_activations` or alter bound criteria even if active form pointers or revisions have since changed or been retired

#### Scenario: Precomputed context is shared across parallel agents
- **WHEN** Layer 3 execution begins
- **THEN** the supervisor SHALL pre-compute rubric and reference context sequentially before dispatching the targeted agent
- **AND** the targeted agent SHALL receive the read-only precomputed context

#### Scenario: Missing or invalid form snapshot fails preparation
- **WHEN** an evaluation job is preparing and an active form snapshot cannot be resolved or fails adapter validation
- **THEN** the job SHALL transition to `FAILED` before worker dispatch and record the snapshot resolution failure
### Requirement: Evaluation outputs are persisted before stopping
The system SHALL persist Layer 3 outputs and associate them with the owning evaluation job, document owner, and exact `evaluation_form_snapshots` records via `form_snapshot_id`. The referenced snapshot evaluation ID and agent identity SHALL match the agent result record. `CriterionScore.criterion_id` SHALL retain its existing meaning as the snapshot's human-readable `criterion_code`; the system SHALL validate the exact criterion-code set against the bound snapshot while retaining rubric criterion UUIDs inside immutable snapshot metadata. Missing, duplicate, or extra criterion scores SHALL fail closed.

Historical evaluations created before dynamic form snapshot persistence that are explicitly marked with `evaluation_jobs.is_pre_snapshot_legacy = TRUE` by a forward migration marker SHALL have a null `form_snapshot_id` and SHALL be labeled `Legacy — form snapshot unavailable` in API and UI metadata without creating a new evaluation job status or using heuristic date/reconstruction logic. Mixed or new evaluations lacking form snapshots SHALL fail closed.

#### Scenario: Layer 3 outputs are stored after parallel completion
- **WHEN** all parallel agent futures complete
- **THEN** the system SHALL persist the outputs through the evaluation data persistence contract sequentially

#### Scenario: Persisted outputs remain tied to the job
- **WHEN** evaluation outputs are saved
- **THEN** the system SHALL associate them with the owning evaluation job and document owner

#### Scenario: Persisted outputs retain form snapshot linkage
- **WHEN** evaluation outputs are saved
- **THEN** the system SHALL associate each agent result with its exact `evaluation_form_snapshots` record via `form_snapshot_id`, verify matching evaluation/agent identity and canonical hash, and validate returned `criterion_code` values against the snapshot

#### Scenario: Historical legacy evaluation is queried
- **WHEN** an authorized user requests an evaluation with `is_pre_snapshot_legacy = TRUE`
- **THEN** the system SHALL return the result with `Legacy — form snapshot unavailable` metadata for its form definition
- **AND** SHALL NOT invent or retroactively attach a dynamic form version

#### Scenario: Non-legacy evaluation missing form snapshot fails closed
- **WHEN** an authorized user requests an evaluation result with `is_pre_snapshot_legacy = FALSE` that lacks a valid bound form snapshot
- **THEN** the system SHALL fail closed with an internal integrity error rather than presenting legacy metadata

### Requirement: Evaluation lifecycle recovery uses CAS and heartbeat-aware transitions
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

### Requirement: Explicit evaluation modes and confirmed program
Evaluation submission SHALL require an explicit `confirmed_program` in `("BSCS", "BSInfoTech")` and an explicit `target_agent` in `("sme", "coordinator", "gad", "itso")`.
- When `target_agent` is `"coordinator"`, the submission SHALL require an authoritative `curriculum_id` or an existing linked curriculum reference on the document.
- When `target_agent` is `"sme"`, `"gad"`, or `"itso"`, the submission SHALL NOT require curriculum references and SHALL execute immediately on the SLM document text.

#### Scenario: Targeted submission for non-coordinator agent succeeds without curriculum
- **WHEN** an authenticated user submits an evaluation with `target_agent` as `"gad"`, `"sme"`, or `"itso"` without specifying a `curriculum_id`
- **THEN** the system SHALL accept the evaluation, schedule only that agent, and execute immediately without partial-mode warnings or curriculum validation errors

#### Scenario: Coordinator submission without curriculum fails closed
- **WHEN** an authenticated user submits an evaluation with `target_agent` as `"coordinator"` but the SLM lacks a linked curriculum reference and no valid `curriculum_id` is supplied
- **THEN** the system SHALL reject the submission with HTTP 422 Unprocessable Entity stating that curriculum context is required for Program Coordinator evaluation
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
