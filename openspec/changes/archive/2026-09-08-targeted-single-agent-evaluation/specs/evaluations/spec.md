## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: Partial evaluation without curriculum mode
**REASON**: Single-agent evaluations are independent domain assessments that are 100% complete for the executed domain. Curriculum context is strictly a Coordinator prerequisite; GAD, ITSO, and SME evaluations do not require curriculum references or partial-intent flags.
