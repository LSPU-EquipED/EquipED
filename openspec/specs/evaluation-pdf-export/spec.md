## Purpose

Define truthful, privacy-safe PDF exports for terminal evaluation results.

## Requirements

### Requirement: Authorized users can export truthful evaluation PDFs
The system SHALL allow an authorized evaluation-result viewer to download a per-agent or consolidated PDF only from an already-authorized terminal evaluation result. The export SHALL use the existing result payload and SHALL NOT introduce a separate content-sharing service.

#### Scenario: Authorized terminal result is exported
- **WHEN** an authorized user selects an export action for a terminal evaluation result
- **THEN** the system SHALL download a PDF derived from that result's currently displayed data
- **AND** the system SHALL not make an additional external request containing evaluation content

#### Scenario: Non-terminal result cannot be exported
- **WHEN** an evaluation is still processing
- **THEN** the system SHALL not offer a PDF export action

### Requirement: PDF score values retain their canonical meaning
The system SHALL render agent criterion and subtotal values using the canonical 1–4 evaluation scale and SHALL label any monitoring-matrix percentage as a distinct 0–100 value. The PDF SHALL use the existing score and adjectival-rating rules and SHALL NOT compute an aggregate from fields with different scales.

#### Scenario: Agent score is rendered
- **WHEN** a PDF includes a criterion or agent subtotal
- **THEN** the system SHALL display its 1–4 scale and its corresponding adjectival rating when available

#### Scenario: Monitoring percentage is available
- **WHEN** a monitoring-matrix percentage is included in a PDF
- **THEN** the system SHALL label it as a percentage separately from 1–4 agent scores

### Requirement: PDF reports represent incomplete results honestly
The system SHALL derive report completeness from persisted evaluation and agent states. It SHALL visibly identify deliberate partial evaluations, accidental failures, skipped agents, unavailable values, and the applicable partial reason. It SHALL omit unavailable institutional metadata rather than hard-coding it.

#### Scenario: Deliberate no-curriculum partial result is exported
- **WHEN** a completed result is marked partial because curriculum review was deliberately omitted
- **THEN** the PDF SHALL identify it as a partial advisory result
- **AND** the Coordinator section SHALL state that it was skipped rather than display a fabricated score

#### Scenario: Agent failed during evaluation
- **WHEN** an agent result is unavailable because that agent failed
- **THEN** the PDF SHALL show the agent as unavailable with the safe result explanation
- **AND** SHALL not label the overall report as fully complete

### Requirement: PDF content is resilient and privacy-safe
The system SHALL render Unicode-capable text, continue generating a text header when an optional logo cannot load, and sanitize narrative content before export. Exported narrative SHALL not expose raw chunk identifiers and SHALL be bounded so content can paginate reliably.

#### Scenario: Filipino text is exported
- **WHEN** a document or evaluation narrative contains Filipino characters or Unicode punctuation
- **THEN** the generated PDF SHALL preserve the readable characters

#### Scenario: Optional logo cannot load
- **WHEN** the institutional logo asset is unavailable
- **THEN** the system SHALL generate the PDF with a text-only header

#### Scenario: Narrative contains an internal chunk token
- **WHEN** an exported justification or evidence string contains a raw chunk identifier token
- **THEN** the PDF SHALL omit that token while retaining the readable narrative

### Requirement: PDF exports are regression-tested
The system SHALL test export data assembly for score scale, report state, unavailable metadata, narrative sanitization, and safe asset failure. The system SHALL also provide browser smoke coverage for per-agent and consolidated report downloads.

#### Scenario: Regression suite exercises a partial report
- **WHEN** export tests run for a partial result with a skipped Coordinator
- **THEN** the tests SHALL assert that the report model identifies partial state and does not include a Coordinator score
