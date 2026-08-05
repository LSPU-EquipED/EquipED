# reference-library Specification

## Purpose
Defines the admin-managed local reference library for institutional syllabus and policy documents after curriculum references are retired.

## Requirements

### Requirement: Admin reference library lists syllabus and policy documents
The system SHALL provide an admin-only reference library listing for `syllabus` and `policy` documents. Curriculum and rubric PDF documents SHALL NOT appear in the active library. Policy references SHALL include a policy-area classification for criterion-targeted ITSO retrieval.

#### Scenario: Admin lists active references
- **WHEN** an authenticated admin requests the reference library
- **THEN** the system SHALL return only syllabus and policy documents with metadata, processing status, and local health indicators

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
The system SHALL allow authenticated users to preview syllabus PDFs according to shared-reference access rules. Policy preview SHALL remain admin-only and SLM preview SHALL remain owner-only. Curriculum preview is retired with curriculum source removal.

#### Scenario: Faculty requests a policy PDF
- **WHEN** an authenticated faculty user requests a policy PDF
- **THEN** the system SHALL deny access without disclosing its existence

#### Scenario: User previews another user's SLM PDF
- **WHEN** an authenticated user requests an SLM PDF they do not own
- **THEN** the system SHALL deny access and SHALL NOT disclose the file path

#### Scenario: Local PDF is missing
- **WHEN** a preview request targets a document whose local PDF file is missing
- **THEN** the system SHALL return a clear not-found response

### Requirement: Admin delete and rebuild manage active references
The system SHALL allow admins to delete and rebuild embeddings for syllabus and policy references only. Curriculum lifecycle actions are retired; the dedicated maintenance purge owns legacy curriculum removal.

#### Scenario: Admin rebuilds a syllabus or policy
- **WHEN** an admin requests rebuild for a syllabus or policy with stored chunks
- **THEN** the system SHALL rebuild only that document's local vectors

### Requirement: Admin UI exposes reference lifecycle actions
The admin frontend SHALL provide a Reference Library page showing references and policy documents with health, preview, rebuild, and delete actions.

#### Scenario: Admin views reference library page
- **WHEN** an admin opens the Reference Library page
- **THEN** the UI SHALL show syllabus and policy references with metadata and health status

#### Scenario: Admin previews from library
- **WHEN** an admin chooses Preview for a reference or policy
- **THEN** the UI SHALL open the PDF using the backend file endpoint

#### Scenario: Admin deletes from library
- **WHEN** an admin confirms Delete for a reference or policy
- **THEN** the UI SHALL call the delete endpoint and refresh the library list after completion

#### Scenario: Admin rebuilds from library
- **WHEN** a reference or policy has missing Chroma vectors but stored chunks
- **THEN** the UI SHALL offer a Rebuild embeddings action

### Requirement: Ready syllabi are available to the SME alignment selector
The system SHALL expose an authenticated, read-only list of admin-managed syllabus references that are ready in both authoritative SQL outcome storage and the local Chroma reference collection. Faculty access to this list SHALL NOT grant upload, rebuild, or delete permissions.

#### Scenario: Faculty opens the SME alignment selector
- **WHEN** an authenticated faculty evaluation owner requests available syllabi
- **THEN** the system SHALL return only processed syllabus documents with persisted outcome rows and local Chroma vectors
- **AND** SHALL exclude curricula, policies, failed syllabi, and syllabi with missing vectors
