# curriculum-reference-extraction Specification

## Purpose
Defines the established extraction behavior for multi-program CCS curriculum references before document chunking and vector store embedding.

## Requirements

### Requirement: Curriculum ingestion uses layout-aware extraction strategies
The system SHALL try curriculum-specific extraction before generic document chunking. It SHALL first attempt single-course-per-page extraction and, only when that produces no course records, attempt multi-program curriculum-map extraction. If both strategies produce no records, it SHALL fall back to the existing generic page-chunking path.

#### Scenario: Single-course CMO layout is recognized
- **WHEN** a curriculum PDF contains course-specification pages with a Course Name heading
- **THEN** the system SHALL create one curriculum record per recognized course page using the course name and the label/value content for that page

#### Scenario: Single-course extraction finds no records
- **WHEN** single-course-per-page extraction produces no course records
- **THEN** the system SHALL attempt multi-program curriculum-map extraction before generic document chunking

#### Scenario: No specialized layout is recognized
- **WHEN** neither specialized curriculum extraction strategy produces records
- **THEN** the system SHALL process the curriculum through generic document page chunking without failing the upload solely for that reason

### Requirement: Multi-program curriculum maps are scoped by selected program
The system SHALL identify curriculum-map sections from a case-insensitive heading equivalent to `Curriculum Map for the Bachelor of Science in <program>` and retain only pages in sections whose program name matches the selected program's extraction keywords. It SHALL stop retaining a section when it reaches the document's curriculum-map end marker, including headings equivalent to `Section 11` or `Sample Means of Curriculum Delivery`.

#### Scenario: Selected Computer Science program limits map pages
- **WHEN** a curriculum reference is uploaded with program `BSCS`
- **THEN** the system SHALL retain only the Curriculum Map section whose header matches `computer science`

#### Scenario: Selected Information Technology program limits map pages
- **WHEN** a curriculum reference is uploaded with program `BSInfoTech`
- **THEN** the system SHALL retain only the Curriculum Map section whose header matches `information technology`

#### Scenario: Map section ends
- **WHEN** the extractor reaches a recognized curriculum-map end marker
- **THEN** it SHALL stop including subsequent pages from that section unless a later matching section header begins a new eligible section

### Requirement: CCS curriculum extraction maps canonical program codes safely
The system SHALL map canonical program code `BSCS` to the keyword `computer science` and canonical program code `BSInfoTech` to the keyword `information technology`. It SHALL normalize program-code input by trimming and comparing case-insensitively. An unknown or absent program value SHALL use both keyword sets rather than include unrelated program sections.

#### Scenario: Program code normalization
- **WHEN** the selected program is supplied as `bsinfotech` with surrounding whitespace
- **THEN** the system SHALL use the `information technology` extraction keyword

#### Scenario: Program is absent or unknown
- **WHEN** the selected program is absent or not one of the canonical mapping codes
- **THEN** the system SHALL include only sections matching `computer science` or `information technology`

#### Scenario: Information Systems section is present
- **WHEN** a multi-program CMO includes an Information Systems section
- **THEN** the system SHALL exclude that section from the current CCS curriculum extraction path

### Requirement: Multi-program CMO extraction preserves truthful granularity
The system SHALL store eligible multi-program curriculum-map content as one record per source page. It SHALL not fabricate per-course row records when OCR or selectable-text ordering cannot reliably associate learning outcomes with an individual course row. Each stored record SHALL retain its source page number and identify the matched program and any detectable course codes in its title.

#### Scenario: Multi-column OCR order is unreliable
- **WHEN** a curriculum-map page contains a multi-column table whose row values cannot be reliably associated after extraction
- **THEN** the system SHALL preserve the eligible page as one retrievable record instead of assigning its content to inferred individual courses

#### Scenario: Course codes are detectable on a selected page
- **WHEN** a retained curriculum-map page contains recognizable course codes
- **THEN** the generated record title SHALL include the matched program and the detected codes

### Requirement: Curriculum-specific OCR is used only for required layout recovery
The system SHALL preserve the existing layout-aware OCR behavior for specialized curriculum extraction. It SHALL use the page's selectable text when available and invoke OCR for map-page text below the specialized selectable-text threshold or for course-specification label/value recovery. Specialized OCR limitations SHALL NOT cause the system to invent a more precise course mapping.

#### Scenario: Scanned multi-program map page
- **WHEN** a curriculum-map page has insufficient selectable text
- **THEN** the system SHALL recover text through the specialized map extraction path before applying its section-header filter
