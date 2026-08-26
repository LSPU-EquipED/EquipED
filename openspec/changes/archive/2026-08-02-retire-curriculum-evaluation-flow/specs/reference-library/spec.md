## MODIFIED Requirements

### Requirement: Admin reference library lists syllabus and policy documents
The system SHALL provide an admin-only reference library listing for `syllabus`
and `policy` documents. Curriculum and rubric PDF documents SHALL NOT appear in
the active library. Policy references SHALL include a policy-area classification
for criterion-targeted ITSO retrieval.

#### Scenario: Admin lists active references
- **WHEN** an authenticated admin requests the reference library
- **THEN** the system SHALL return only syllabus and policy documents with
  metadata, processing status, and local health indicators

### Requirement: Reference PDF preview streams stored local files
The system SHALL allow authenticated users to preview syllabus PDFs according to
shared-reference access rules. Policy preview SHALL remain admin-only and SLM
preview SHALL remain owner-only. Curriculum preview is retired with curriculum
source removal.

#### Scenario: Faculty requests a policy PDF
- **WHEN** an authenticated faculty user requests a policy PDF
- **THEN** the system SHALL deny access without disclosing its existence

### Requirement: Admin delete and rebuild manage active references
The system SHALL allow admins to delete and rebuild embeddings for syllabus and
policy references only. Curriculum lifecycle actions are retired; the dedicated
maintenance purge owns legacy curriculum removal.

#### Scenario: Admin rebuilds a syllabus or policy
- **WHEN** an admin requests rebuild for a syllabus or policy with stored chunks
- **THEN** the system SHALL rebuild only that document's local vectors
