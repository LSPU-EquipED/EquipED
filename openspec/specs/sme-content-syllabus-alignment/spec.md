# SME Content-Syllabus Alignment Specification

## Purpose
Define a transparent, non-scoring SME advisory check that determines whether substantial SLM content is within the scope of the selected syllabus outcomes.

## Requirements

### Requirement: Syllabus ingestion retains only the outcomes table
The system SHALL deterministically locate the standard LSPU `Course Outcomes` or `Course Learning Outcomes` table, SHALL persist one page-attributed chunk per valid outcome row, and SHALL embed only those rows in the local syllabus collection. The original PDF SHALL remain available through the authenticated reference preview contract.

#### Scenario: Standard outcomes table is extracted
- **WHEN** an admin uploads a syllabus containing one recognized outcomes table with outcome-code and outcome-description columns
- **THEN** the system SHALL persist each outcome description verbatim with its code, row order, page number, and OCR attribution
- **AND** SHALL NOT persist or embed unrelated syllabus content

#### Scenario: Outcomes table is unavailable or ambiguous
- **WHEN** no valid outcomes table is found, no valid rows are extracted, or multiple candidate tables are ambiguous
- **THEN** syllabus preprocessing SHALL fail closed
- **AND** the syllabus SHALL NOT become retrieval-ready

### Requirement: Extracted outcomes are transparently viewable
The system SHALL provide authenticated users an ordered view of the extracted outcomes for a shared syllabus reference, including outcome code, verbatim text, source page, extraction method, and chunk identifier.

#### Scenario: Authenticated user views extracted outcomes
- **WHEN** an authenticated user requests the outcomes of a stored syllabus
- **THEN** the system SHALL return the persisted rows in source order
- **AND** SHALL preserve access to the original locally stored PDF for comparison

### Requirement: SME syllabus alignment is explicitly started and isolated from scoring
The system SHALL run content-syllabus alignment only after an authenticated owner explicitly starts it from the SME interface. Normal multi-agent evaluation and SME rubric scoring SHALL NOT invoke, await, or depend on syllabus alignment. Once started, the standalone process SHALL identify substantial SLM topics from direct SLM input, retrieve candidate outcomes only from that syllabus document, and classify each topic as aligned or not aligned using cited SLM and syllabus evidence. This advisory output SHALL NOT add a rubric criterion, change the SME subtotal, change synthesis weights, or change evaluation job status.

#### Scenario: Normal evaluation runs
- **WHEN** an evaluation executes SME rubric scoring
- **THEN** the system SHALL NOT execute content-syllabus alignment
- **AND** SME scoring SHALL complete independently

#### Scenario: User starts alignment from SME interface
- **WHEN** the evaluation owner activates the content-syllabus alignment action for an evaluation with a selected syllabus and completed SME result
- **THEN** the system SHALL start alignment as a separate background process
- **AND** SHALL expose its independent running, completed, or failed state

#### Scenario: Every substantial topic is aligned
- **WHEN** every identified SLM topic is supported by at least one selected-syllabus outcome
- **THEN** the advisory status SHALL be `MEETS`

#### Scenario: Some substantial topics are aligned
- **WHEN** at least one but not every identified SLM topic is supported
- **THEN** the advisory status SHALL be `PARTIALLY_MEETS`

#### Scenario: No substantial topic is aligned
- **WHEN** topics are identified but none are supported
- **THEN** the advisory status SHALL be `DOES_NOT_MEET`

#### Scenario: Alignment cannot be evaluated
- **WHEN** no syllabus is selected or extraction, retrieval, or advisory analysis is unavailable
- **THEN** the advisory status SHALL be `UNAVAILABLE` with a reason
- **AND** otherwise successful SME rubric scoring SHALL continue unchanged

### Requirement: Alignment output is persisted and exposed
The system SHALL persist the bounded structured alignment artifact separately from provenance and expose it in the SME domain result. The artifact SHALL include the overall statement and status, topic totals, matched outcomes, unmatched topics, and source identifiers. Generated alignment remains advisory and human review remains authoritative.

#### Scenario: Evaluation results are loaded later
- **WHEN** a completed evaluation is retrieved
- **THEN** the same persisted SME alignment artifact SHALL be returned without rerunning alignment
