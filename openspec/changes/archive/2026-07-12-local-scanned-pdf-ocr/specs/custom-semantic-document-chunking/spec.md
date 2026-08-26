## MODIFIED Requirements

### Requirement: New uploads use deterministic semantic chunking
The system SHALL chunk newly uploaded PDF pages with a local deterministic, structure-aware chunker that prefers headings, paragraphs, and lists before falling back to sentence and word splitting. Before chunking, the system SHALL extract complete usable text from every nonblank page through embedded-text extraction or the local OCR capability, and SHALL fail preprocessing rather than chunk an incomplete document.

#### Scenario: Structured page is chunked by document structure
- **WHEN** a newly uploaded PDF page contains recognizable headings, paragraphs, or list blocks
- **THEN** the system SHALL form chunks from those structural units before considering sentence-only splitting

#### Scenario: Weak structure falls back safely
- **WHEN** a page contains little or unreliable structure
- **THEN** the system SHALL fall back to sentence splitting and, if necessary, word-tail splitting instead of failing the upload

#### Scenario: Required page text cannot be extracted
- **WHEN** a nonblank page cannot yield usable embedded or local OCR text
- **THEN** the system SHALL fail preprocessing for the document
- **AND** SHALL NOT create chunks from only the remaining pages
