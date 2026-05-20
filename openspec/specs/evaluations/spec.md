# evaluations Specification

## Purpose
Define the evaluation job contract for the current phase, including Layer 3 execution, persistence of evaluation outputs, and honest stopping before Layer 4 report generation.

## Requirements

### Requirement: Evaluation jobs progress into Layer 3
The system SHALL support evaluation job submission, pre-agent processing, and execution of the Layer 3 multi-agent evaluation boundary.

#### Scenario: Evaluation job is accepted and begins processing
- **WHEN** an authenticated user submits a new evaluation request for a document they own
- **THEN** the system SHALL create an evaluation job in `SUBMITTED` state and continue into the pre-agent processing stages

#### Scenario: Layer 3 execution starts after pre-agent processing
- **WHEN** an evaluation job completes the pre-agent stages
- **THEN** the system SHALL enter Layer 3 multi-agent evaluation and record progress without claiming the job is complete

### Requirement: Evaluation outputs are persisted before stopping
The system SHALL persist Layer 3 outputs for the evaluation job before the workflow stops at the unimplemented Layer 4 boundary.

#### Scenario: Layer 3 outputs are stored
- **WHEN** Layer 3 finishes producing evaluation outputs
- **THEN** the system SHALL persist the outputs through the evaluation data persistence contract

#### Scenario: Persisted outputs remain tied to the job
- **WHEN** evaluation outputs are saved
- **THEN** the system SHALL associate them with the owning evaluation job and document owner

### Requirement: Evaluation stops honestly before Layer 4
The system SHALL stop evaluation jobs after persisting Layer 3 outputs and SHALL not fabricate report generation, scorecard completion, matrix updates, or `COMPLETED` status.

#### Scenario: Layer 4 is not entered
- **WHEN** Layer 3 persistence succeeds
- **THEN** the system SHALL end the job with an explicit non-complete terminal outcome and a reason that Layer 4 is not implemented

#### Scenario: No downstream artifacts are generated
- **WHEN** a job reaches the end of the current workflow
- **THEN** the system SHALL not create a report, finalize a scorecard, update the monitoring matrix, or mark the job `COMPLETED`

### Requirement: Evaluation polling is limited to the owning user
The system SHALL only expose evaluation status for jobs owned by the authenticated user who is polling them.

#### Scenario: User polls their own job
- **WHEN** an authenticated user requests the status of an evaluation job they created
- **THEN** the system SHALL return that job's current state and progress information

#### Scenario: User attempts to poll another user's job
- **WHEN** an authenticated user requests the status of an evaluation job owned by a different user
- **THEN** the system SHALL deny access and SHALL not disclose the other job's status

### Requirement: Evaluation lifecycle status sequence
Evaluation jobs SHALL progress through the following status sequence: `SUBMITTED` → `PREPROCESSING` → `EVALUATING` → `SYNTHESIZING` → `COMPLETED`. Jobs that encounter errors SHALL transition to `FAILED` from any non-terminal status. The `EMBEDDING` status SHALL NOT be used — embedding occurs at document upload time for reference and rubric documents, not during evaluation.

#### Scenario: Job progresses through lifecycle
- **WHEN** an evaluation job is submitted and accepted
- **THEN** the system SHALL transition through `SUBMITTED` → `PREPROCESSING` → `EVALUATING` → `SYNTHESIZING` → `COMPLETED` (or `FAILED` on error)

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
