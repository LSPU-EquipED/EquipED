# reference-library Specification

## Purpose
Defines the admin-managed local reference library for institutional syllabus, curriculum, and policy documents, including health tracking, file preview, rebuild, deletion, and faculty evaluation discovery.

## Requirements

### Requirement: Admin reference library lists syllabus and policy documents
The system SHALL provide an admin-only reference library listing for `syllabus`, `curriculum`, and `policy` documents. Rubric PDF documents SHALL NOT appear in the active library. Curriculum references SHALL include their canonical BSCS or BSInfoTech program. Policy references SHALL include a policy-area classification for criterion-targeted ITSO retrieval.

#### Scenario: Admin lists active references
- **WHEN** an authenticated admin requests the reference library
- **THEN** the system SHALL return syllabus, curriculum, and policy documents with metadata, processing status, and local health indicators

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
The system SHALL allow authenticated users to preview syllabus and curriculum PDFs according to institution-shared reference access rules. Policy preview SHALL remain admin-only and SLM preview SHALL remain owner-only.

#### Scenario: Faculty previews a curriculum PDF
- **WHEN** authenticated faculty previews a curriculum exposed through program-matched evaluation setup
- **THEN** the system SHALL stream the locally stored curriculum PDF without granting lifecycle permissions

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
The system SHALL allow admins to rebuild embeddings for syllabus, curriculum, and policy references and to delete references that are not referenced by any evaluation. Ordinary curriculum deletion SHALL block on every evaluation reference, including terminal jobs, and SHALL fail observably without deleting the SQL row when local vector cleanup fails. Historical nullable curriculum links SHALL be preserved.

#### Scenario: Admin rebuilds a reference
- **WHEN** an admin requests rebuild for a syllabus, curriculum, or policy with stored chunks
- **THEN** the system SHALL rebuild only that document's local vectors

#### Scenario: Admin deletes a curriculum reference
- **WHEN** an admin confirms deletion of a curriculum that is not referenced by any evaluation and vector cleanup succeeds
- **THEN** the system SHALL remove that reference through the source-appropriate local lifecycle and refresh the library

#### Scenario: Completed evaluation references curriculum
- **WHEN** an admin requests ordinary deletion of a curriculum referenced by a terminal evaluation
- **THEN** the system SHALL block deletion and preserve the curriculum link and historical evaluation

#### Scenario: Vector cleanup fails
- **WHEN** local vector deletion fails during ordinary curriculum deletion
- **THEN** the system SHALL report failure and SHALL NOT delete the curriculum SQL row or chunks

### Requirement: Admin UI exposes reference lifecycle actions
The admin frontend SHALL provide a Reference Library page showing syllabus, curriculum, and policy documents with health, preview, rebuild, and delete actions. Curriculum rows SHALL display their canonical program.

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

### Requirement: Ready syllabi are available to the SME alignment selector
The system SHALL expose an authenticated, read-only list of admin-managed syllabus references that are ready in both authoritative SQL outcome storage and the local Chroma reference collection. Faculty access to this list SHALL NOT grant upload, rebuild, or delete permissions.

#### Scenario: Faculty opens the SME alignment selector
- **WHEN** an authenticated faculty evaluation owner requests available syllabi
- **THEN** the system SHALL return only processed syllabus documents with persisted outcome rows and local Chroma vectors
- **AND** SHALL exclude curricula, policies, failed syllabi, and syllabi with missing vectors

### Requirement: Ready curricula are available to evaluation setup
The system SHALL expose an authenticated, ownership-scoped curriculum suggestion read model for a faculty-owned SLM and explicitly confirmed program. Before validating program or querying curriculum, it SHALL resolve the target as an owned SLM and return the same masked not-found response for missing, foreign, or non-SLM IDs. It SHALL return only curriculum documents for the matching canonical program and SHALL derive readiness through the documents-owned curriculum-readiness service. Faculty curriculum discovery SHALL remain excluded from the generic document-list endpoint.

#### Scenario: Faculty requests curriculum suggestions
- **WHEN** authenticated faculty requests suggestions for their SLM and confirmed `BSCS` or `BSInfoTech` program
- **THEN** the system SHALL return matching curriculum references and SHALL mark only processed, chunked, locally embedded entries selectable

#### Scenario: Faculty requests suggestions for another user's SLM
- **WHEN** authenticated faculty requests curriculum suggestions for an SLM they do not own
- **THEN** the system SHALL deny access without revealing curriculum or SLM existence

#### Scenario: Faculty requests suggestions for a non-SLM target
- **WHEN** authenticated faculty supplies a syllabus, curriculum, policy, or missing document ID
- **THEN** the system SHALL return the same masked not-found response used for a foreign SLM before program validation

#### Scenario: Unsupported program is requested
- **WHEN** curriculum suggestions for an owned SLM are requested for an unsupported program
- **THEN** the system SHALL reject the request without returning unrelated curricula

#### Scenario: Faculty lists generic documents
- **WHEN** a faculty user calls the generic document-list endpoint
- **THEN** the system SHALL NOT expose curriculum references through that list
