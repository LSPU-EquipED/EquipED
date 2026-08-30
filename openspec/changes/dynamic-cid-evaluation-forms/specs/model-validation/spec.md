## MODIFIED Requirements

### Requirement: Expected scores remain independent of model evaluation
Expected scores SHALL be entered separately for every criterion defined in the bound form revision for SME, Coordinator, GAD, and ITSO (or for SME, GAD, and ITSO in explicit partial validation), SHALL use the institutional integer scale from 1 to 4, and SHALL NOT be included in agent prompts, retrieval context, or automated score calculation.

The Model Validation catalog SHALL return the exact active `rubric_set_id`, revision version, and rubric criterion UUID, code, title, domain, and display order for each active agent. Model validation benchmark submission SHALL echo the `rubric_set_id` and rubric criterion UUIDs alongside the expected scores.

Under activation-first and deterministic revision row locks (`rubric_agent_activations` row followed by affected `rubric_sets` revision rows in sorted order), validation submission SHALL verify that the echoed revisions are the currently active published compatible revisions and that the submitted criterion UUID set matches the revision's criterion UUID set exactly. The submission SHALL create the standard `EvaluationJob` and persist standard `evaluation_form_snapshots` for those exact revisions in the same transaction. Evaluation preparation and recovery SHALL reuse these precreated standard snapshots without re-resolving active pointers, ensuring that subsequent form activation or retirement cannot alter an accepted benchmark. A bound revision MAY execute after later retirement; retirement affects future selection only, not immutable in-flight snapshots. No separate benchmark binding table or format SHALL be introduced.

Partial mode SHALL bind SME, GAD, and ITSO form revisions and require no curriculum input; full mode SHALL require normal explicit curriculum selection and bind SME, GAD, ITSO, and Coordinator form revisions. The system SHALL reject incomplete, duplicate, unknown, foreign, or out-of-range expected criterion scores.

#### Scenario: Expected score is recorded
- **WHEN** a benchmark is submitted with complete valid expected criterion scores for all criteria across echoed active published revisions
- **THEN** the system SHALL verify echoed revisions and criterion UUID sets under activation-first locks
- **AND** SHALL create the EvaluationJob and persist standard `evaluation_form_snapshots` in the same transaction
- **AND** SHALL snapshot the agent, criterion code, criterion title, and expected score

#### Scenario: Expected score is recorded for full evaluation benchmark
- **WHEN** an admin submits a full benchmark with explicit curriculum selection and complete valid expected criterion scores across SME, Coordinator, GAD, and ITSO echoed published revisions
- **THEN** the system SHALL verify active revisions, persist standard `evaluation_form_snapshots` for SME, Coordinator, GAD, and ITSO, and create criterion benchmark rows for all four agents
- **AND** later retirement or activation of forms SHALL NOT alter the accepted benchmark snapshot criteria

#### Scenario: Expected score is recorded for partial evaluation benchmark
- **WHEN** an admin submits a partial benchmark without curriculum and provides complete valid expected scores for all criteria across SME, GAD, and ITSO echoed published revisions
- **THEN** the system SHALL persist standard `evaluation_form_snapshots` for SME, GAD, and ITSO, create criterion benchmark rows for active partial agent criteria, and truthfully omit Coordinator expectations, snapshots, and execution

#### Scenario: Expected score is outside the scale
- **WHEN** a submitted expected criterion score is below 1 or above 4
- **THEN** the system SHALL reject the request

#### Scenario: Benchmark submitted with mismatched or inactive revision
- **WHEN** an admin submits a benchmark echoing a revision or criterion UUID set that is not currently active, not published, or modified
- **THEN** the system SHALL reject the submission under lock and prevent benchmark job creation

#### Scenario: Admin enters criterion scores efficiently
- **WHEN** an admin types into an expected-score control
- **THEN** the control SHALL accept exactly one digit from 1 through 4
- **AND** SHALL ignore other characters and additional digits
- **AND** mouse-wheel and arrow-key actions SHALL NOT change the score
- **WHEN** the admin presses Enter in a score control that has another score after it
- **THEN** focus SHALL move to the next expected-score control

### Requirement: Validation preserves Admin SLM upload without curriculum selection
Model Validation SHALL retain its Admin SLM upload workflow but SHALL NOT offer curriculum suggestions or require a curriculum selection for a new validation. New validation runs without curriculum SHALL use explicit partial semantics, bind exact SME, GAD, and ITSO published form revisions into standard snapshots, and truthfully omit Coordinator expectations and execution.

#### Scenario: Admin validates an uploaded SLM
- **WHEN** an admin uploads an SLM for model validation without curriculum
- **THEN** the validation workflow SHALL not request a curriculum suggestion, SHALL bind exact SME, GAD, and ITSO form revisions into standard snapshots, and SHALL not require Coordinator expected scores
