# curriculum-reference-extraction Specification

## Purpose
Defines the admin-only curriculum reference PDF ingestion, program validation, fail-closed extraction, local reference indexing, and readiness for selection.

## Requirements

### Requirement: Curriculum ingestion is admin-only and program-scoped
The system SHALL accept curriculum PDF ingestion only from administrators and SHALL require canonical program context limited to explicit write values `BSCS` or `BSInfoTech`. It SHALL accept `BSIT` only when reading or filtering legacy data and SHALL reject `BSIT` and unsupported programs on upload before extraction.

#### Scenario: Admin uploads a supported curriculum
- **WHEN** an administrator uploads a curriculum PDF tagged `BSCS` or `BSInfoTech`
- **THEN** the system SHALL accept it into the curriculum reference ingestion workflow

#### Scenario: Unsupported curriculum program is supplied
- **WHEN** a curriculum upload is tagged with any program outside BSCS or BSInfoTech
- **THEN** the system SHALL reject it before extraction, chunking, or embedding

#### Scenario: Legacy alias is used on upload
- **WHEN** a curriculum upload is tagged `BSIT`
- **THEN** the system SHALL reject the write and require canonical `BSInfoTech`

### Requirement: Curriculum ingestion uses fail-closed local extraction
The system SHALL extract complete usable text through embedded-text extraction or local OCR, SHALL apply deterministic page-bounded semantic chunking, and SHALL fail the curriculum document rather than persist partial or degraded extraction output.

#### Scenario: Required curriculum page cannot be extracted
- **WHEN** a nonblank curriculum page cannot yield usable embedded or local OCR text
- **THEN** the system SHALL mark ingestion failed, persist no partial chunk set, and schedule no embedding

#### Scenario: Curriculum extraction succeeds
- **WHEN** every required page yields usable text
- **THEN** the system SHALL persist page-bounded curriculum chunks and index them in the local reference collection

### Requirement: Multi-program curriculum maps are filtered by selected program
When curriculum-map section headers are present, the system SHALL trim extracted text at section boundaries before chunking and retain only text belonging to the selected canonical program, including when two program sections share one page. Program headers SHALL be recognized case-insensitively from headings equivalent to `Curriculum Map for the Bachelor of Science in <program>`; selected sections SHALL stop at the next program header or headings equivalent to `Section 11` or `Sample Means of Curriculum Delivery`. If a selected section is absent, or another-program indicators exist but boundaries cannot be resolved, ingestion SHALL fail rather than retain mixed-program content. A document with no program-map headers and no other-program indicators SHALL be treated as an administrator-tagged single-program curriculum.

#### Scenario: BSCS section is selected from a multi-program PDF
- **WHEN** a `BSCS` curriculum PDF contains Computer Science, Information Technology, and Information Systems map sections
- **THEN** the system SHALL retain only the Computer Science section pages

#### Scenario: BSInfoTech section is selected from a multi-program PDF
- **WHEN** a `BSInfoTech` curriculum PDF contains multiple program map sections
- **THEN** the system SHALL retain only the Information Technology section pages

#### Scenario: Selected section is absent
- **WHEN** map section headers are detected but none matches the selected canonical program
- **THEN** the system SHALL fail ingestion without falling back to all pages

#### Scenario: Program boundary occurs within one page
- **WHEN** selected-program text and the next program header occur on the same extracted page
- **THEN** the system SHALL retain only text before that next header and SHALL exclude the neighboring program section before chunking

#### Scenario: Multi-program indicators are unrecognized
- **WHEN** extracted text indicates another academic program but deterministic program boundaries cannot be resolved
- **THEN** the system SHALL fail ingestion rather than classify the PDF as single-program

#### Scenario: Single-program curriculum has no map headers
- **WHEN** a curriculum PDF contains no recognizable multi-program map section headers and no other-program indicators
- **THEN** the system SHALL retain all successfully extracted pages under the administrator-confirmed program

### Requirement: Ready curriculum references are selectable
The documents module SHALL own one curriculum-readiness service used by both curriculum suggestions and evaluation admission. A curriculum SHALL be selectable only when it has current administrator provenance, `source_type=curriculum`, a canonical program matching the request, `PROCESSED` status, non-empty persisted chunks, and live vector availability in the local curriculum reference collection. The persisted `chroma_stored` flag alone SHALL NOT establish readiness.

#### Scenario: Curriculum is ready
- **WHEN** a supported curriculum has processed chunks and local vectors
- **THEN** the system SHALL expose it as selectable for its matching program

#### Scenario: Curriculum is not ready
- **WHEN** processing failed or required local vectors are missing
- **THEN** the system SHALL report it unavailable and SHALL NOT accept it for a full evaluation

#### Scenario: Stored flag is stale
- **WHEN** a curriculum has `chroma_stored=true` but no live local vectors
- **THEN** the readiness service SHALL report it unavailable

#### Scenario: Legacy faculty curriculum row exists
- **WHEN** a processed curriculum row was not uploaded by an administrator
- **THEN** the readiness service SHALL exclude it from suggestions and full evaluation admission
