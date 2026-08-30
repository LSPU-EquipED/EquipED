## MODIFIED Requirements

### Requirement: Precomputed context is shared across parallel agents
The supervisor SHALL pre-compute rubric form snapshots and reference context sequentially on the orchestrator thread before dispatching agents in parallel. Snapshot creation SHALL support two explicit paths:
1. Normal evaluations SHALL resolve complete structured form snapshots for all scheduled agents from `rubric_agent_activations` in a single database transaction coordinated with the `EVALUATING` transition and persist them into `evaluation_form_snapshots` with `UNIQUE(evaluation_id, agent_id)`.
2. Model Validation evaluations SHALL reuse the standard `evaluation_form_snapshots` precreated during benchmark submission and SHALL NEVER reread `rubric_agent_activations` during preparation or recovery.

If any scheduled agent snapshot is missing, partial, duplicate, wrong-agent, hash-mismatched, or invalid, preparation SHALL fail closed before worker dispatch. All parallel agents SHALL receive the same read-only precomputed context and recursively immutable frozen form snapshot DTOs in memory, and SHALL NOT perform worker-side database queries for rubric or form definitions.

Dynamic domain and criterion display order SHALL be reconstructed directly from verified immutable snapshots. Persisted `CriterionScore.criterion_id` values SHALL match exact snapshot `criterion_code` values; missing, duplicate, or extra scores SHALL fail closed.

#### Scenario: Precomputed context and form snapshots are resolved before dispatch
- **WHEN** Layer 3 parallel execution begins for a normal evaluation
- **THEN** the supervisor SHALL resolve and persist complete immutable form snapshots with verified canonical hashes for each active agent on the main thread in a single transaction coordinated with the EVALUATING transition
- **AND** all agents SHALL receive the precomputed reference context and frozen form snapshot DTOs without worker-side database lookups

#### Scenario: Supervisor reuses precreated snapshots without rereading activations
- **WHEN** Layer 3 parallel execution begins for an evaluation with precreated standard snapshots (such as a Model Validation benchmark run)
- **THEN** the supervisor SHALL load and verify the existing `evaluation_form_snapshots` bound to the evaluation job
- **AND** SHALL NOT reread `rubric_agent_activations` or alter bound criteria even if active form pointers or revisions have since changed or been retired

#### Scenario: Precomputed context is shared across parallel agents
- **WHEN** Layer 3 parallel execution begins
- **THEN** the supervisor SHALL pre-compute rubric and reference context sequentially before dispatching agents in parallel
- **AND** all agents SHALL receive the same read-only precomputed context

#### Scenario: Missing or invalid form snapshot fails preparation
- **WHEN** an evaluation job is preparing and an active form snapshot cannot be resolved or fails adapter validation
- **THEN** the job SHALL transition to `FAILED` before worker dispatch and record the snapshot resolution failure

### Requirement: Persisted outputs remain tied to the job
The system SHALL persist Layer 3 outputs and associate them with the owning evaluation job, document owner, and exact `evaluation_form_snapshots` records via `form_snapshot_id`. The referenced snapshot evaluation ID and agent identity SHALL match the agent result record. `CriterionScore.criterion_id` SHALL retain its existing meaning as the snapshot's human-readable `criterion_code`; the system SHALL validate the exact criterion-code set against the bound snapshot while retaining rubric criterion UUIDs inside immutable snapshot metadata. Missing, duplicate, or extra criterion scores SHALL fail closed.

Historical evaluations created before dynamic form snapshot persistence that are explicitly marked with `evaluation_jobs.is_pre_snapshot_legacy = TRUE` by a forward migration marker SHALL have a null `form_snapshot_id` and SHALL be labeled `Legacy — form snapshot unavailable` in API and UI metadata without creating a new evaluation job status or using heuristic date/reconstruction logic. Mixed or new evaluations lacking form snapshots SHALL fail closed.

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
