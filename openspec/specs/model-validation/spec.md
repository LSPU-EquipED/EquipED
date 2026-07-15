# model-validation Specification

## Purpose

Define an admin-only benchmark workflow that compares every normal SLM evaluation criterion with an independently supplied human expected score.

## Requirements

### Requirement: Model validation is restricted to administrators

The system SHALL expose Model Validation under the admin dashboard and SHALL reject access by faculty users.

#### Scenario: Admin opens Model Validation

- **WHEN** an authenticated admin opens the Model Validation section
- **THEN** the system SHALL present the benchmark evaluation workflow and prior benchmark runs

#### Scenario: Faculty attempts access

- **WHEN** an authenticated faculty user attempts to access Model Validation
- **THEN** the system SHALL deny access

### Requirement: A benchmark uses the normal evaluation pipeline

The system SHALL evaluate the selected admin-owned SLM through the existing evaluation job workflow and SHALL NOT create a separate ingestion, chunking, or scoring engine. Model Validation SHALL read the same document chunks and invoke the same supervisor and SME, Coordinator, GAD, and ITSO implementations as faculty evaluation. Separation SHALL apply only to the admin workspace and dedicated validation benchmark records.

#### Scenario: Admin starts a benchmark

- **WHEN** an admin supplies an SLM, required curriculum selection or explicit partial intent, and expected scores for every active agent criterion
- **THEN** the system SHALL create and execute a normal evaluation job
- **AND** SHALL associate the benchmark record with that evaluation job

#### Scenario: Uploaded SLM is not yet processed

- **WHEN** the Model Validation upload is still pending document processing
- **THEN** the client SHALL keep the start action disabled and refresh the document status
- **AND** SHALL enable validation only after the SLM is processed with stored text chunks

#### Scenario: Uploaded SLM processing fails

- **WHEN** the Model Validation upload reports failed document processing
- **THEN** the client SHALL show the processing failure instead of presenting the SLM as ready
- **AND** SHALL NOT submit a validation job for that document

#### Scenario: Scanned SLM is prepared for validation

- **WHEN** an admin uploads a scanned or mixed-content SLM through Model Validation
- **THEN** the client SHALL use the same shared document-upload API as the normal SLM workflow
- **AND** the server SHALL apply the local scanned-PDF OCR contract before the document can be validated

### Requirement: Model Validation shows honest per-agent activity

The Model Validation workspace SHALL show separate progress indicators for SME, Coordinator, GAD, and ITSO while a validation job is active. The indicators SHALL derive from the shared evaluation lifecycle and SHALL NOT claim individual completion before agent outputs are persisted.

#### Scenario: Agents are evaluating in parallel

- **WHEN** the linked evaluation job is in `EVALUATING`
- **THEN** each participating agent SHALL display an active loading indicator
- **AND** the display SHALL explain that Model Validation uses the same scoring pipeline as faculty evaluation

#### Scenario: Evaluation is preparing or synthesizing

- **WHEN** the linked job is in `SUBMITTED` or `PREPROCESSING`
- **THEN** participating agents SHALL display as queued
- **WHEN** the linked job reaches `SYNTHESIZING`
- **THEN** participating agents SHALL display that agent scoring is complete

#### Scenario: Partial validation omits Coordinator

- **WHEN** an admin explicitly runs validation without a curriculum
- **THEN** Coordinator SHALL display as skipped rather than loading

### Requirement: Expected scores remain independent of model evaluation

Expected scores SHALL be entered separately for every active SME, Coordinator, GAD, and ITSO criterion, SHALL use the institutional integer scale from 1 to 4, and SHALL NOT be included in agent prompts, retrieval context, or automated score calculation. The system SHALL reject incomplete, duplicate, unknown, or out-of-range expected criterion scores.

#### Scenario: Expected score is recorded

- **WHEN** a benchmark is submitted with complete valid expected criterion scores
- **THEN** the system SHALL create one criterion benchmark row per agent criterion
- **AND** SHALL snapshot the agent, criterion code, criterion title, and expected score

#### Scenario: Expected score is outside the scale

- **WHEN** a submitted expected criterion score is below 1 or above 4
- **THEN** the system SHALL reject the request

#### Scenario: Admin enters criterion scores efficiently

- **WHEN** an admin types into an expected-score control
- **THEN** the control SHALL accept exactly one digit from 1 through 4
- **AND** SHALL ignore other characters and additional digits
- **AND** mouse-wheel and arrow-key actions SHALL NOT change the score
- **WHEN** the admin presses Enter in a score control that has another score after it
- **THEN** focus SHALL move to the next expected-score control

### Requirement: Model validation data uses dedicated tables

The system SHALL persist run-level Model Validation metadata in `model_validations` and criterion-level expected and actual score pairs in `model_validation_criterion_scores`. Criterion benchmark data SHALL NOT be stored on the normal evaluation job or criterion score tables.

#### Scenario: Validation run is stored

- **WHEN** an admin submits a valid Model Validation run
- **THEN** the system SHALL create one `model_validations` row linked to the normal evaluation job
- **AND** SHALL create its criterion benchmark rows in `model_validation_criterion_scores`

### Requirement: Completed benchmarks show score agreement

The system SHALL persist and show each expected criterion score beside the corresponding actual agent criterion score and absolute error after evaluation results are available.

#### Scenario: Benchmark evaluation completes

- **WHEN** the linked evaluation produces criterion scores
- **THEN** Model Validation SHALL match results by agent and criterion code
- **AND** SHALL persist actual scores and absolute errors on the corresponding criterion benchmark rows

### Requirement: Model validation reports operational and safety metrics

The system SHALL compute evaluation latency, score-class perplexity, and a contextual toxicity estimate for completed validation runs. Score-class perplexity SHALL be `exp(mean absolute score error)` over the institutional 1–4 scale so that a perfect score match has perplexity 1.00. Toxicity SHALL be assessed dynamically from generated summaries and justifications by the configured local or self-hosted LLM backend, with a numeric score, bounded label, concise explanation, and model provenance persisted on the validation record.

#### Scenario: Completed run contributes metrics

- **WHEN** a validation evaluation completes with persisted agent output
- **THEN** its job duration SHALL contribute to mean latency
- **AND** its absolute score error SHALL contribute to score-class perplexity
- **AND** its generated summaries and justifications SHALL be assessed contextually for toxicity

#### Scenario: Contextual toxicity assessment fails

- **WHEN** the configured classifier is unavailable or returns an invalid result
- **THEN** the system SHALL preserve the completed SLM evaluation
- **AND** SHALL record the toxicity assessment as unavailable without inventing a score

### Requirement: Score agreement has a confusion matrix

The system SHALL aggregate all available expected and actual criterion-score pairs into a 4×4 confusion matrix with expected classes as rows and predicted classes as columns.

The Model Validation page SHALL derive accuracy, macro precision, and macro recall from the displayed confusion matrix and SHALL present the three values as circular percentage visualizations. Macro precision and macro recall SHALL average only score classes that have an available denominator; when the matrix contains no comparisons, the visualizations SHALL show that the metrics are unavailable rather than inventing zero-percent performance.

#### Scenario: Validation analytics are displayed

- **WHEN** at least one completed validation exists
- **THEN** the admin SHALL see latency, score-class perplexity, toxicity, and the confusion matrix together as a visual interpretation
- **AND** the confusion matrix SHALL show circular accuracy, macro precision, and macro recall summaries calculated from its counts

#### Scenario: Validation analytics have no compared scores

- **WHEN** the confusion matrix contains no expected and predicted score pairs
- **THEN** accuracy, macro precision, and macro recall SHALL be displayed as unavailable

### Requirement: Performance analytics lead the Model Validation workspace

The Model Validation page SHALL display the performance metric summary and confusion matrix before the validation data-entry workflow. The data-entry workflow SHALL be collapsible and keyboard operable so that it does not dominate the workspace while an admin reviews results.

#### Scenario: Admin reviews Model Validation

- **WHEN** an admin opens the Model Validation page
- **THEN** performance metrics and the confusion matrix SHALL appear above validation input and history
- **AND** the new-validation input SHALL be collapsed until the admin expands it

#### Scenario: Admin enters validation data

- **WHEN** an admin expands the new-validation input
- **THEN** all required SLM, program, and criterion-level expected-score controls SHALL be available
