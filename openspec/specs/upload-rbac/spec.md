# upload-rbac Specification

## Purpose
Restricts document intake to active source types after curriculum and rubric PDF ingestion is retired. Faculty uploads are SLM-only, Admin Ingestion accepts syllabus and policy, and policy remains admin-only with no-existence-leak.

## Requirements
### Requirement: Restrict institutional document uploads to admins
The system MUST restrict active institutional ingestion to administrators. Faculty users MUST only upload `slm` documents. Admin Ingestion MUST accept only `syllabus` and `policy` documents; direct upload requests for `curriculum` or any rubric PDF source type MUST be rejected for every role. Admin SLM upload for Model Validation remains an allowed separate workflow. Syllabus documents are institution-shared references, while policy documents remain admin-only and are available only through the residency-gated ITSO evidence path.

#### Scenario: Retired document type is uploaded
- **WHEN** any authenticated user uploads a document with source type `curriculum` or a rubric PDF type
- **THEN** the system SHALL reject the request with a clear validation error

#### Scenario: Faculty uploads an SLM
- **WHEN** an authenticated faculty user uploads an SLM
- **THEN** the system SHALL accept only the SLM workflow

#### Scenario: Admin uploads an active institutional document
- **WHEN** an authenticated admin uploads a syllabus or policy document through Admin Ingestion
- **THEN** the system SHALL process it in its source-appropriate local store
