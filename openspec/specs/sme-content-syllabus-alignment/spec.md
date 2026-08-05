# SME Content-Syllabus Alignment Specification

## Purpose
Define a transparent, non-scoring SME advisory check that determines whether substantial SLM content is within the selected syllabus course contents.

## Requirements

### Requirement: Syllabus ingestion retains only the Course Contents column
The system SHALL use PyMuPDF table detection to locate one unambiguous syllabus table containing a `Course Contents` column, SHALL persist page-attributed chunks derived only from cells beneath that column, and SHALL embed only those chunks in the local syllabus collection. The original PDF SHALL remain available through the authenticated reference preview contract.

#### Scenario: Standard Course Contents column is extracted
- **WHEN** an admin uploads a syllabus containing one recognized table with a `Course Contents` column
- **THEN** the system SHALL persist the normalized text beneath that column with row order, page number, and OCR attribution
- **AND** SHALL NOT persist or embed unrelated syllabus content

#### Scenario: Headerless table continues onto the next page
- **WHEN** a recognized Course Contents table continues on an immediately succeeding page without repeating its column headers
- **THEN** the system SHALL identify the continuation by compatible table and target-column geometry
- **AND** SHALL continue extracting only the cells occupying the Course Contents column

#### Scenario: Course Contents table is unavailable or ambiguous
- **WHEN** no valid Course Contents table is found, no valid target-column cells are extracted, or multiple candidate or continuation tables are ambiguous
- **THEN** syllabus preprocessing SHALL fail closed
- **AND** the syllabus SHALL NOT become retrieval-ready

### Requirement: Extracted course contents are transparently viewable
The system SHALL provide authenticated users an ordered view of the extracted course-content chunks for a shared syllabus reference, including content reference, text, source page, extraction method, and chunk identifier.

#### Scenario: Authenticated user views extracted course contents
- **WHEN** an authenticated user requests the course contents of a stored syllabus
- **THEN** the system SHALL return the persisted rows in source order
- **AND** SHALL preserve access to the original locally stored PDF for comparison

### Requirement: SME syllabus alignment is explicitly started and isolated from scoring
The system SHALL expose an owner-scoped Syllabus Alignment workspace listing the authenticated user's SLM documents. An owner MAY explicitly select a processed SLM and a retrieval-ready syllabus from the admin-managed shared reference library and start alignment without first running rubric scoring. The standalone process SHALL use the SME model-routing configuration, identify the substantive instructional concepts actually covered across the complete direct SLM input, compare each concept against the complete Course Contents list from only the explicitly selected syllabus document, and classify each topic as aligned or not aligned using cited SLM and syllabus evidence. The selected syllabus Course Contents SHALL act as a one-way allow-list: syllabus items not addressed by the SLM SHALL NOT reduce alignment, while substantive SLM content not explicitly listed or clearly encompassed by any syllabus item SHALL be outside the syllabus. Normal multi-agent evaluation and SME rubric scoring SHALL NOT invoke, await, persist, or expose syllabus alignment. This advisory output SHALL NOT add a rubric criterion, change any agent result, change synthesis weights, or change evaluation job status.

#### Scenario: Normal evaluation runs
- **WHEN** an evaluation executes SME rubric scoring
- **THEN** the system SHALL NOT execute content-syllabus alignment
- **AND** SME scoring SHALL complete independently

#### Scenario: User starts alignment from the standalone workspace
- **WHEN** the owner selects a processed SLM and an available syllabus reference and activates the alignment action
- **THEN** the system SHALL start alignment as a separate background process
- **AND** SHALL scope retrieval and evidence to the submitted syllabus ID
- **AND** SHALL expose its independent running, completed, or failed state
- **AND** SHALL NOT require an evaluation job or SME scoring result

#### Scenario: User selects an available syllabus
- **WHEN** the owner opens the standalone Syllabus Alignment workspace
- **THEN** the system SHALL list only admin-uploaded syllabus references that are processed, contain extracted course-content chunks, and have vectors in the local reference collection
- **AND** SHALL require a selection before alignment can start

#### Scenario: User views available SLMs
- **WHEN** an authenticated user opens the Syllabus Alignment workspace
- **THEN** the system SHALL list only SLM documents owned by that user
- **AND** SHALL identify documents that have not finished processing as unavailable for alignment

#### Scenario: Submitted syllabus is not retrieval-ready
- **WHEN** the submitted document is missing, is not a syllabus, lacks extracted course-content chunks, or has no vectors in the local reference collection
- **THEN** the system SHALL reject the request without changing evaluation status or scores

#### Scenario: Every substantial topic is aligned
- **WHEN** every identified SLM topic is supported by at least one selected-syllabus course-content chunk
- **THEN** the advisory status SHALL be `MEETS`

#### Scenario: Syllabus contains content not taught in the SLM
- **WHEN** one or more selected-syllabus Course Contents entries are absent from the SLM
- **THEN** those absent syllabus entries SHALL NOT reduce the SLM alignment level

#### Scenario: SLM contains an incidental mention
- **WHEN** a concept is only named but is not explained, demonstrated, practiced, or assessed
- **THEN** the concept SHALL NOT be counted as a substantive SLM topic

#### Scenario: Extracted text is a statement rather than a topic
- **WHEN** a model returns a sentence, direction, learning objective, or copied claim as a topic label
- **THEN** the system SHALL repair it to a concise grounded concept label or discard it
- **AND** SHALL preserve exact SLM evidence and source attribution

#### Scenario: Some substantial topics are aligned
- **WHEN** at least one but not every identified SLM topic is supported
- **THEN** the advisory status SHALL be `PARTIALLY_MEETS`

#### Scenario: No substantial topic is aligned
- **WHEN** topics are identified but none are supported by the selected syllabus course contents
- **THEN** the advisory status SHALL be `DOES_NOT_MEET`

#### Scenario: Alignment cannot be evaluated
- **WHEN** no syllabus is selected or extraction, retrieval, or advisory analysis is unavailable
- **THEN** the advisory status SHALL be `UNAVAILABLE` with a reason
- **AND** otherwise successful SME rubric scoring SHALL continue unchanged

### Requirement: Alignment output is persisted and exposed
The system SHALL persist one current result per SLM in a dedicated syllabus-alignment table that has no dependency on evaluation jobs or agent results. The persisted output SHALL separate the overall alignment level and detailed justification from bounded topic evidence and model provenance. It SHALL include topic totals, matched course-content chunks, unmatched topics, source identifiers, lifecycle timestamps, and the SME-configured model used. Generated alignment remains advisory and human review remains authoritative.

#### Scenario: Alignment result is loaded later
- **WHEN** the owner retrieves the current alignment result
- **THEN** the same persisted alignment artifact SHALL be returned without rerunning alignment

#### Scenario: Alignment is rerun
- **WHEN** an owner starts another alignment after an earlier run is terminal
- **THEN** the system SHALL warn that the stored result will be permanently replaced
- **AND** SHALL reset and reuse the SLM's current alignment row for the new run
- **AND** SHALL NOT retain the earlier alignment artifact as run history

#### Scenario: Alignment result is reported
- **WHEN** a completed result is viewed or exported
- **THEN** the system SHALL present the alignment level, aligned and total topic counts, a detailed justification, aligned topics, topics outside the syllabus, cited evidence, and advisory status
- **AND** the full report SHALL separate aligned topics and topics outside the syllabus in a two-column review layout
- **AND** the PDF export SHALL use a formal CID review-form layout with institutional identity, document metadata, findings, and human-review sign-off fields
