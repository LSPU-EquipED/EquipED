## Purpose

Define the lifecycle, administrative authoring, typed scoring strategies, agent capability manifests, and immutable revision management for dynamic Curriculum Instruction Development (CID) evaluation forms.

## ADDED Requirements

### Requirement: Admin management of dynamic CID evaluation forms and revisions
The system SHALL support dynamic Curriculum Instruction Development (CID) evaluation forms for each agent (`agent_id` for SME, Coordinator, GAD, ITSO) through `rubric_sets` representing versioned revisions with status `draft | published | retired` enforced by a database CHECK constraint, and independent per-agent atomic activation via `rubric_agent_activations(agent_id PK, rubric_set_id FK, updated_by, updated_at)` enforced by a composite foreign key guaranteeing same-agent targets. The lifecycle API SHALL operate as a thin service façade wrapping repository queries and row locking primitives without a generic workflow engine. `updated_by` SHALL be nullable only for migration/system seed rows; every normal admin activation operation SHALL require a non-null authenticated admin actor. At most one editable draft revision SHALL exist per agent, enforced by a partial unique index. Published revision child content SHALL be immutable. An admin MAY transition a non-active published revision to `retired`. Active revisions SHALL NOT be retired until another compatible published revision is activated. Retired revisions SHALL NOT be activated or edited, and their historical data SHALL remain. Retirement SHALL affect future selection only; in-flight evaluations or benchmarks bound to an immutable snapshot whose source revision is later retired SHALL continue execution without change. Deleting a draft revision SHALL delete only its draft domains and criteria without modifying published revisions. Rollback SHALL be performed by activating an older still-published compatible revision.

Lifecycle concurrency SHALL use a shared locking protocol: every draft child mutation, bulk reorder, and publication operation SHALL acquire an exclusive row lock on the parent `rubric_sets` row before checking status or modifying children; activation, retirement, and combined publish+activate operations SHALL acquire an exclusive lock on the agent's `rubric_agent_activations` row first, followed by all affected `rubric_sets` revision rows in deterministic `rubric_set_id` sort order to eliminate race conditions and deadlocks.

Bulk reordering SHALL be ordering-only and SHALL submit a complete ordered tree of domain and criterion IDs. The system SHALL validate that all submitted IDs belong to the draft, contain no duplicates, leave no domain or criterion omitted, and retain every criterion under its existing domain; criterion reparenting across domains SHALL be rejected atomically. Adding, removing, or moving criteria between domains SHALL remain explicit mutation endpoints.

#### Scenario: Admin creates a new draft revision from active revision
- **WHEN** an authenticated admin creates a draft revision for an agent's evaluation form
- **THEN** the system SHALL clone the currently active published revision into a single editable draft revision with an incremented version number
- **AND** the draft SHALL remain invisible to live evaluation execution until published and activated

#### Scenario: Admin edits and reorders domains and criteria in draft
- **WHEN** an authenticated admin adds, removes, edits, or submits an atomic ordering-only bulk reorder of a complete ordered domain and criterion tree within an editable draft
- **THEN** the system SHALL acquire a row lock on the parent draft `rubric_sets` row, verify complete tree integrity with no reparenting, missing, duplicate, or foreign IDs, and persist the updates to the draft revision's domains and criteria
- **AND** existing published revisions SHALL remain unmodified

#### Scenario: Admin attempts criterion reparenting or incomplete bulk reorder
- **WHEN** an admin submits a bulk reorder that attempts to move a criterion to a different domain, omits an existing ID, contains duplicates, or contains foreign IDs
- **THEN** the system SHALL reject the reorder atomically under parent lock and leave the draft order unchanged

#### Scenario: Admin attempts in-place mutation of a published revision
- **WHEN** an admin attempts to update, delete, or reorder domains and criteria on a published revision
- **THEN** the system SHALL reject the request with HTTP 409 Conflict indicating published revisions are immutable

#### Scenario: Admin publishes and activates a compatible revision
- **WHEN** an authenticated admin publishes a draft revision that passes the target agent capability manifest validation
- **THEN** the system SHALL execute the shared locking protocol and transition the revision status to published with `published_at` and non-null `published_by` recorded
- **AND** SHALL update `rubric_agent_activations` for that agent to point to the newly published revision with non-null `updated_by` and `updated_at` recorded

#### Scenario: Admin retires a non-active published revision
- **WHEN** an authenticated admin retires a published revision that is not currently active
- **THEN** the system SHALL lock the activation row and revision row in deterministic order, transition the revision status to `retired` with `retired_at` and non-null `retired_by` recorded
- **AND** SHALL prevent future activation or drafting from that retired revision while retaining all history

#### Scenario: Admin attempts to retire an active revision
- **WHEN** an authenticated admin attempts to retire a revision currently referenced in `rubric_agent_activations`
- **THEN** the system SHALL reject the request with HTTP 409 Conflict requiring another compatible published revision to be activated first

#### Scenario: Admin rolls back active revision to a prior compatible revision
- **WHEN** an authenticated admin activates a previously published compatible revision that is not retired
- **THEN** the system SHALL update `rubric_agent_activations` for that agent to point to the selected prior revision with non-null `updated_by`
- **AND** SHALL retain all published revision history unmodified

#### Scenario: Non-admin attempts form management
- **WHEN** a non-admin user attempts to create, edit, validate, publish, activate, retire, or roll back a form revision
- **THEN** the system SHALL deny access with HTTP 403 Forbidden

### Requirement: Registered typed scoring strategies
The system SHALL evaluate criteria using an allowlisted set of registered typed scoring strategies: `llm_rubric_guidance` (bounded validated LLM-assigned 1–4 score), `count_band` (deterministic count thresholds with explicit `minimum_count` or `maximum_count` mode), `ratio_band` (deterministic ratio band supporting `coverage_percentage` and `absolute_difference` modes with bounded optional small-sample issue-count override), and `curriculum_alignment` (Coordinator-only). Strategy configurations SHALL use strict discriminated unions with unknown fields forbidden, bounded nesting depth, bounded array lengths, bounded string lengths, bounded total serialized size per config/request/revision/snapshot, finite numeric values, and monotonic non-overlapping bands covering institutional scores 1–4. Strategy configurations SHALL NOT contain provider, model, endpoint, URL, tool, template expression, or prompt role controls. Prompt templates for `llm_rubric_guidance` SHALL structurally delimit untrusted input and explicitly forbid treating source documents as instructions. Active GAD and ITSO managed prompts SHALL provide criterion-agnostic task framing only; fixed criterion identifiers in managed prompts SHALL fail closed, and all per-criterion authority SHALL come exclusively from the bound form snapshot. Local LLM invocations SHALL enforce fixed byte-capped response reads alongside configuration maxima (32768 output tokens, 3600 second timeout) without adding a new configuration knob. Structurally valid but ungrounded model outputs SHALL be recorded as ungrounded advisory flags. Bounded schema validation SHALL be revalidated at draft save, locked publication, activation, and snapshot load.

#### Scenario: Criterion configured with valid typed scoring strategy
- **WHEN** an admin configures a criterion with a supported strategy key and conforming JSON configuration parameters
- **THEN** the system SHALL accept and persist the strategy configuration

#### Scenario: Criterion configured with unsupported strategy, malformed parameters, or invalid score coverage
- **WHEN** an admin configures a criterion with an unknown strategy key, overlapping score bands, or parameters violating strategy schemas
- **THEN** the system SHALL reject the configuration with a structured validation error and prevent publication

### Requirement: Agent capability manifests and pure form validation
The system SHALL require each draft form revision to pass pure structural validation against its target agent capability manifest via `validate_form(form, manifest)` before it can be published or activated. The system SHALL enforce four immutable capability manifests without plugin registries or inheritance:
- **SME Manifest v1**: Allows `llm_rubric_guidance`, `count_band` in `minimum_count` mode, and `ratio_band`; requires 1–20 unique criteria; measurement input shapes are score/evidence, grounded instance list, or grounded qualifying/total units. Ratio config supports `coverage_percentage` and optional short-sample override.
- **GAD Manifest v1**: Allows `count_band` in `maximum_count` mode for grounded adverse-instance lists and `ratio_band` for paired female/male counts using `absolute_difference` mode; requires 1–10 unique criteria. Revision 1 SHALL preserve GAD-01 maximum-count thresholds 0/1/3 for scores 4/3/2 and GAD-03/04/05 thresholds 0/2/5, with larger counts scoring 1.
- **ITSO Manifest v1**: Allows `llm_rubric_guidance`; requires 1–10 unique criteria.
- **Coordinator Manifest v1**: Allows exactly 1 criterion with `curriculum_alignment` (A-05); expansion to multi-criterion Coordinator forms requires a new adapter manifest version.

SME, GAD, and ITSO adapter v1 SHALL accept genuinely new criterion codes when the configured strategy maps to an existing supported measurement shape. The criterion's snapshot-bound title, description, scoring rule, guidance, thresholds, domain, and display order SHALL define its bounded extraction and scoring contract; runtime execution SHALL NOT require a code-specific plugin or executable formula. Criterion codes SHALL be globally unique case-insensitively within a form. A criterion requiring a new measurement shape, or any Coordinator expansion beyond A-05, SHALL require a new adapter version.

#### Scenario: Draft revision passes agent capability manifest validation
- **WHEN** an admin validates a draft revision whose structure and strategy types conform to the agent capability manifest and prompt budget
- **THEN** the system SHALL return a successful validation result with the estimated serialized prompt-character budget contribution

#### Scenario: Admin adds a criterion using an existing measurement shape
- **WHEN** an admin adds a new SME, GAD, or ITSO criterion code whose strategy and mode map to an existing measurement shape supported by that agent manifest
- **THEN** the system SHALL validate and execute the criterion from its snapshot metadata without requiring a code deployment

#### Scenario: Admin requests unsupported extraction semantics
- **WHEN** a criterion requires a measurement shape not supported by the active adapter manifest version
- **THEN** publication SHALL fail with a structured adapter-compatibility error until a new adapter version is deployed

#### Scenario: Draft revision violates agent capability manifest constraints
- **WHEN** an admin attempts to publish a draft revision containing unsupported strategies for the target agent or exceeding prompt budget bounds
- **THEN** the system SHALL reject publication, provide detailed validation errors, and keep the revision in draft state

### Requirement: Structured evaluation form snapshot resolution before dispatch
The evaluation supervisor SHALL resolve complete structured form snapshots for all scheduled agents in a single main-thread database transaction coordinated with the job row lock and transition into `EVALUATING` after full/partial determination. The resolved form snapshot payloads, revision numbers, canonical SHA-256 hashes, and adapter keys/versions SHALL be persisted into `evaluation_form_snapshots` with `UNIQUE(evaluation_id, agent_id)`. The canonical hash SHALL be computed from deterministic UTF-8 JSON with sorted keys covering `evaluation_id`, `agent_id`, `rubric_set_id`/revision identity, `adapter_key`, `adapter_version`, and ordered domain/criterion/strategy definitions. Duplicated snapshot columns (`evaluation_id`, `agent_id`, `rubric_set_id`, `adapter_key`, `adapter_version`, `snapshot_hash`) SHALL strictly equal their canonical hashed payload values at creation, dispatch, retry/recovery, and `AgentResult` persistence. If any scheduled agent snapshot is missing, partial, duplicate, wrong-agent, hash-mismatched, or column-mismatched, the entire preparation transaction SHALL fail closed. Parallel agent workers SHALL receive only recursively immutable frozen DTOs with zero database queries for form definitions during scoring.

#### Scenario: Pre-dispatch atomic snapshot binding
- **WHEN** an evaluation job is prepared for Layer 3 execution
- **THEN** the supervisor SHALL query active published form revisions from `rubric_agent_activations` for all scheduled agents, verify canonical hashes and column/payload equality, persist complete snapshots into `evaluation_form_snapshots`, and pass immutable frozen DTOs to worker threads

#### Scenario: Missing, partial, or hash-invalid active form snapshot fails job preparation
- **WHEN** an evaluation job is initiated but an active published form revision is missing, incomplete, hash-mismatched, or column-mismatched for a scheduled agent
- **THEN** the system SHALL transition the job to `FAILED` during preparation before dispatching any worker threads and record the snapshot resolution error

#### Scenario: Retry and recovery reuses existing snapshots
- **WHEN** an evaluation job is retried or recovered after an interrupted run
- **THEN** the system SHALL reuse the existing `evaluation_form_snapshots` bound to the evaluation job, verify canonical hashes, column equality, and complete sets, and SHALL NOT re-resolve current active pointer revisions
