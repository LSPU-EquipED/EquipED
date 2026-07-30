# reference-library Specification

## Purpose
Defines the admin-managed local reference library for institutional syllabus, curriculum, and policy documents.

## Requirements

### Requirement: Admin reference library lists syllabus, curriculum, and policy documents
The system SHALL provide an admin-only reference library listing for documents with source types `syllabus`, `curriculum`, and `policy`. Rubric documents SHALL NOT be included in this library. Curriculum references SHALL include program metadata to support program-driven suggestion. Policy references SHALL include a policy-area classification to support criterion-targeted ITSO retrieval.

#### Scenario: Admin lists references
- **WHEN** an authenticated admin requests the reference library
- **THEN** the system SHALL return syllabus, curriculum, and policy documents with metadata, upload date, processing status, and local health indicators

#### Scenario: Rubrics are excluded
- **WHEN** the reference library contains uploaded rubric documents
- **THEN** the system SHALL exclude `rubric_sme`, `rubric_coord`, `rubric_gad`, and `rubric_itso` documents from the reference library response

#### Scenario: Faculty cannot manage the library
- **WHEN** an authenticated faculty user requests the admin reference library endpoint
- **THEN** the system SHALL deny access

#### Scenario: Curriculum without program is not suggestion-ready
- **WHEN** a curriculum reference has no program metadata
- **THEN** the system SHALL treat it as not eligible for program-driven curriculum suggestion until program metadata is provided

#### Scenario: Policy upload requires classification
- **WHEN** an admin attempts to upload a policy reference without a recognized policy-area classification
- **THEN** the system SHALL reject the upload before processing

### Requirement: Reference health is computed from local storage
The system SHALL compute reference health from current local state rather than storing static health fields. Health SHALL include PDF file availability, DB chunk count, Chroma vector availability, processing status, and derived embedding readiness.

#### Scenario: Reference is fully healthy
- **WHEN** a reference document has a local PDF file, stored chunks, and Chroma vectors
- **THEN** the system SHALL report the reference as ready for retrieval

#### Scenario: PDF file missing locally
- **WHEN** the database row exists but the local PDF file is missing
- **THEN** the system SHALL report the file health as missing without deleting the database row automatically

#### Scenario: Chroma vectors missing locally
- **WHEN** chunks exist in the database but Chroma vectors for the document are missing
- **THEN** the system SHALL report embedding health as missing locally and eligible for rebuild

### Requirement: Reference PDF preview streams stored local files
The system SHALL allow authenticated users to preview syllabus and curriculum PDF files from local storage. Policy PDF preview SHALL be admin-only. SLM PDF preview SHALL remain owner-only.

#### Scenario: Admin previews reference PDF
- **WHEN** an authenticated admin previews a syllabus, curriculum, or policy document
- **THEN** the system SHALL stream the local PDF file with inline PDF content headers

#### Scenario: Faculty previews shared reference PDF
- **WHEN** an authenticated faculty user previews a syllabus or curriculum document
- **THEN** the system SHALL stream the local PDF file if it exists

#### Scenario: Faculty previews policy PDF
- **WHEN** an authenticated faculty user requests a policy PDF
- **THEN** the system SHALL deny access and SHALL NOT disclose the file path

#### Scenario: User previews another user's SLM PDF
- **WHEN** an authenticated user requests an SLM PDF they do not own
- **THEN** the system SHALL deny access and SHALL NOT disclose the file path

#### Scenario: Local PDF is missing
- **WHEN** a preview request targets a document whose local PDF file is missing
- **THEN** the system SHALL return a clear not-found response

### Requirement: Admin delete removes reference assets
The system SHALL allow admins to delete syllabus, curriculum, and policy references. Deletion SHALL clean up the source-specific Chroma vectors, SQL chunks, the document row, and the local PDF file.

#### Scenario: Admin deletes reference
- **WHEN** an authenticated admin deletes a syllabus, curriculum, or policy document
- **THEN** the system SHALL delete its Chroma vectors by `document_id` from the matching collection
- **AND** delete its `DocumentChunk` rows
- **AND** delete its `Document` row
- **AND** delete the local PDF file if present

#### Scenario: Delete tolerates missing local assets
- **WHEN** Chroma vectors or the local PDF file are already missing during deletion
- **THEN** the system SHALL complete deletion of remaining SQL records and report/log the missing asset cleanup outcome

#### Scenario: Referenced reference cannot be deleted
- **WHEN** an authenticated admin attempts to delete a syllabus or curriculum document referenced by one or more evaluation jobs
- **THEN** the system SHALL reject the delete request with a conflict response
- **AND** the system SHALL preserve the document, chunks, Chroma vectors, and local PDF file

#### Scenario: Faculty attempts reference delete
- **WHEN** an authenticated faculty user attempts to delete a reference document
- **THEN** the system SHALL deny access

### Requirement: Admin can rebuild reference embeddings
The system SHALL allow admins to rebuild Chroma embeddings for syllabus, curriculum, and policy documents when database chunks exist. Rebuild SHALL NOT require re-uploading the PDF.

#### Scenario: Admin rebuilds missing Chroma vectors
- **WHEN** a reference or policy document has persisted chunks but missing Chroma vectors
- **THEN** an authenticated admin SHALL be able to trigger embedding rebuild for that document

#### Scenario: Rebuild requires chunks
- **WHEN** a reference or policy document has no stored chunks
- **THEN** the system SHALL reject rebuild with a clear error explaining that chunks are unavailable

#### Scenario: Faculty attempts rebuild
- **WHEN** an authenticated faculty user attempts to rebuild reference or policy embeddings
- **THEN** the system SHALL deny access

### Requirement: Admin UI exposes reference lifecycle actions
The admin frontend SHALL provide a Reference Library page showing references and policy documents with health, preview, rebuild, and delete actions.

#### Scenario: Admin views reference library page
- **WHEN** an admin opens the Reference Library page
- **THEN** the UI SHALL show syllabus, curriculum, and policy references with metadata and health status

#### Scenario: Admin previews from library
- **WHEN** an admin chooses Preview for a reference or policy
- **THEN** the UI SHALL open the PDF using the backend file endpoint

#### Scenario: Admin deletes from library
- **WHEN** an admin confirms Delete for a reference or policy
- **THEN** the UI SHALL call the delete endpoint and refresh the library list after completion

#### Scenario: Admin rebuilds from library
- **WHEN** a reference or policy has missing Chroma vectors but stored chunks
- **THEN** the UI SHALL offer a Rebuild embeddings action

### Requirement: Curriculum references use the curriculum extraction contract
Before embedding a curriculum reference, the system SHALL process it through the `curriculum-reference-extraction` contract. Curriculum-specific extraction SHALL determine chunk semantics; the Reference Library SHALL continue to own reference lifecycle, health, access, preview, deletion, and embedding rebuild behavior.

#### Scenario: Admin ingests a curriculum reference
- **WHEN** an admin uploads a curriculum reference
- **THEN** the system SHALL apply the curriculum extraction contract before persisting chunks and creating reference embeddings

#### Scenario: Curriculum-specific extraction finds no specialized layout
- **WHEN** the curriculum extraction contract falls back to generic page chunking
- **THEN** the Reference Library SHALL persist and manage the resulting curriculum chunks through its existing lifecycle rules
