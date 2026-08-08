# document-metadata-detection Specification

## Purpose
Define the contract for auto-detecting document metadata (program, academic_year, course_code, lesson_title) from uploaded PDF text using deterministic regex pattern matching, without LLM calls.

## Requirements

### Requirement: Regex-based metadata detection
The system SHALL extract `program`, `academic_year`, `course_code`, and `lesson_title` from document text using regex pattern matching during the preprocessing pipeline. Detection SHALL use only the Python `re` module — no LLM calls.

#### Scenario: Program detected from cover page
- **WHEN** a document's first 2-3 pages contain `BSCS`, `BSInfoTech`, or legacy alias `BSIT`
- **THEN** the system SHALL populate the `program` field with the detected code
- **AND** if no known program code is found, `program` SHALL remain null — it is not forced from filename

#### Scenario: Academic year detected from cover page
- **WHEN** a document's first 2-3 pages contain a year range pattern (e.g., "2025-2026", "AY 2025", "Sem/AY: ... 2025-2026")
- **THEN** the system SHALL populate the `academic_year` field with the detected value

#### Scenario: Course code detected from title page
- **WHEN** a document's first 2-3 pages contain a course code pattern (e.g., "CCS 101", "CMSC 313", "IT 201")
- **THEN** the system SHALL populate the `course_code` field with the detected value

#### Scenario: Lesson title detected from cover page
- **WHEN** a document's first 2-3 pages contain a "Lesson Title:" label followed by a value
- **THEN** the system SHALL populate the `lesson_title` field with the detected value
- **AND** if `lesson_title` was manually provided during upload, the detected value SHALL NOT overwrite it

#### Scenario: No metadata detected
- **WHEN** the regex patterns find no matches in the first 2-3 pages
- **THEN** the system SHALL leave `program`, `academic_year`, `course_code`, and `lesson_title` as null
- **AND** the document SHALL still process normally without errors

### Requirement: Detection scans first 2-3 pages only
The system SHALL run regex patterns against text from the first 2-3 pages (approximately 6000 characters) of the extracted document text only. This limits false positives from body text.

#### Scenario: Pattern in body text ignored
- **WHEN** a course code pattern appears on page 15 but not on pages 1-3
- **THEN** the system SHALL NOT detect it as the document's course code

### Requirement: Known program list matching
The system SHALL match only the active program catalog `BSCS` and `BSInfoTech`. The legacy `BSIT` alias SHALL be accepted case-insensitively and canonicalized to `BSInfoTech`; unsupported programs are ignored by detection.

#### Scenario: Known program matched
- **WHEN** the text contains "BSInfoTech" which is in the known program list
- **THEN** the system SHALL detect "BSInfoTech" as the program

#### Scenario: Legacy alias canonicalized
- **WHEN** the text contains "BSIT" and "BSIT" is in the known program list as an alias
- **THEN** the system SHALL detect the program and store the canonical code "BSInfoTech"

#### Scenario: Unknown acronym ignored
- **WHEN** the text contains "PDF" which matches the course code pattern but is not a real program
- **THEN** the system SHALL NOT detect it as a program

### Requirement: Non-blocking detection
Metadata detection SHALL be non-blocking. Detection failures SHALL NOT affect the document's processing status or prevent embedding.

#### Scenario: Detection fails silently
- **WHEN** regex detection raises an exception
- **THEN** the system SHALL catch the exception, log a warning, and continue preprocessing
- **AND** the document's processing status SHALL remain unaffected

### Requirement: Detected metadata persisted to Document
The system SHALL persist detected `program`, `academic_year`, `course_code`, and `lesson_title` to the `Document` model after preprocessing completes.

#### Scenario: Metadata saved after preprocessing
- **WHEN** preprocessing completes and metadata was detected
- **THEN** the Document record SHALL be updated with the detected values

#### Scenario: Existing manual program preserved
- **WHEN** the `program` field was manually set during upload
- **THEN** the system SHALL NOT overwrite it with auto-detected value

#### Scenario: Existing manual lesson_title preserved
- **WHEN** the `lesson_title` field was manually set during upload
- **THEN** the system SHALL NOT overwrite it with auto-detected value
