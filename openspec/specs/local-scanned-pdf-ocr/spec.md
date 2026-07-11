# local-scanned-pdf-ocr Specification

## Purpose
Define the local OCR contract for scanned and image-based PDF uploads, ensuring fail-closed behavior, durable upload ownership, and production provisioning of English and Filipino language support.

## Requirements

### Requirement: Scanned and mixed PDF pages use local OCR
The system SHALL use a local, offline OCR engine to extract text from newly uploaded PDF pages that lack meaningful embedded/selectable text. OCR execution SHALL remain on institution-controlled infrastructure and SHALL NOT transmit PDF page content to an external service.

#### Scenario: Image-only scanned page is uploaded
- **WHEN** a newly uploaded PDF page has no meaningful embedded/selectable text and contains readable raster text
- **THEN** the system SHALL run local OCR for that page
- **AND** SHALL use the extracted text as page input for metadata detection and page-bounded chunking
- **AND** SHALL mark chunks derived from that page as OCR-derived

#### Scenario: Mixed PDF contains selectable and scanned pages
- **WHEN** a newly uploaded PDF contains both pages with meaningful embedded text and pages requiring OCR
- **THEN** the system SHALL preserve embedded text for selectable pages
- **AND** SHALL OCR each page requiring OCR before document preprocessing succeeds

### Requirement: OCR-required page failures prevent incomplete ingestion
The system SHALL NOT mark a document processed, persist chunks, or embed reference content when a nonblank page requiring OCR cannot be read.

#### Scenario: OCR engine is unavailable
- **WHEN** a nonblank page requires OCR and the local OCR executable or required language data is unavailable
- **THEN** the system SHALL fail preprocessing for the upload
- **AND** SHALL return a user-safe error explaining that scanned-PDF OCR is unavailable
- **AND** SHALL NOT persist or embed a partial document

#### Scenario: OCR execution fails for one page of a mixed PDF
- **WHEN** a document contains another successfully extracted page but OCR fails for a required page
- **THEN** the system SHALL fail preprocessing for the complete document
- **AND** SHALL NOT silently omit the unreadable page

#### Scenario: Page is blank
- **WHEN** a page contains no meaningful embedded text and no meaningful raster text
- **THEN** the system SHALL treat the page as blank
- **AND** SHALL allow preprocessing to continue without creating a chunk for that page

### Requirement: Upload artifacts have durable ownership before file creation
The system SHALL establish durable ownership tracking before creating an uploaded PDF artifact so interrupted OCR uploads can be recovered without untracked files, chunks, or vectors.

#### Scenario: Database-backed upload starts
- **WHEN** a database-backed upload is accepted for processing
- **THEN** the system SHALL commit a `PENDING` document record with its deterministic artifact path before opening or writing the PDF
- **AND** `PROCESSED` SHALL be the finalization point at which document metadata and chunks become visible together

#### Scenario: Database-backed upload is interrupted
- **WHEN** a database-backed upload is interrupted after its `PENDING` record exists but before finalization
- **THEN** startup recovery SHALL remove its tracked artifact when present
- **AND** SHALL mark the document `FAILED`
- **AND** SHALL ensure no chunks or vectors remain for the interrupted upload

#### Scenario: Upload runs without a database
- **WHEN** an upload runs in no-database development mode
- **THEN** the system SHALL create a durable local ownership marker before opening the PDF artifact
- **AND** restart recovery SHALL remove marker-owned artifacts because in-memory document metadata is ephemeral

#### Scenario: Immediate cleanup fails
- **WHEN** an OCR upload fails and its artifact cannot be deleted immediately
- **THEN** the system SHALL retain durable ownership tracking for later recovery
- **AND** SHALL NOT report the artifact as successfully processed

### Requirement: Local OCR runtime is provisioned and validated
The supported production deployment SHALL provide the local OCR executable and English (`eng`) and Filipino (`fil`) language data. The system SHALL expose readiness diagnostics that verify the executable and configured languages before accepting scanned PDFs.

#### Scenario: Production OCR runtime is ready
- **WHEN** the server starts in a production deployment profile
- **THEN** readiness diagnostics SHALL verify that the configured OCR executable can run
- **AND** SHALL verify that English and Filipino language packs are available

#### Scenario: Development runs without OCR
- **WHEN** a development text-only profile does not provide the local OCR runtime
- **THEN** the application SHALL remain usable for text-based PDFs
- **AND** SHALL reject scanned-PDF uploads with an actionable OCR-unavailable error

### Requirement: OCR resource usage is bounded
The system SHALL bound local OCR resource use for uploaded PDFs to protect the single-process application from excessive rasterization or concurrent OCR work. The initial supported limits SHALL be 25 OCR-candidate pages per document, 200 DPI, 8 million pixels per page, 20 seconds per page, one concurrent OCR worker, and a 30-second worker-acquisition limit.

#### Scenario: OCR candidate page is rasterized
- **WHEN** the system rasterizes a page for local OCR
- **THEN** it SHALL use configured resolution or pixel bounds
- **AND** SHALL fail safely with an actionable upload error when configured OCR limits are exceeded

#### Scenario: OCR call exceeds its execution limit
- **WHEN** local OCR exceeds its configured execution time limit
- **THEN** the system SHALL fail preprocessing without persisting partial chunks or embeddings
- **AND** SHALL return a user-safe error that the scanned page could not be read
