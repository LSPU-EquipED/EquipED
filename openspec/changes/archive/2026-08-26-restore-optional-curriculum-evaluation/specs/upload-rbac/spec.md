## MODIFIED Requirements

### Requirement: Restrict institutional document uploads to admins
The system MUST restrict active institutional ingestion to administrators. Faculty users MUST only upload `slm` documents. Admin Ingestion MUST accept `syllabus`, `curriculum`, and `policy` documents; curriculum upload writes MUST require explicit canonical `BSCS` or `BSInfoTech` and MUST reject legacy alias `BSIT`. Direct upload requests for any rubric PDF source type MUST be rejected for every role. Admin SLM upload for Model Validation remains an allowed separate workflow. Syllabus and curriculum documents are institution-shared references, while policy documents remain admin-only and are available only through the residency-gated ITSO evidence path.

#### Scenario: Retired rubric type is uploaded
- **WHEN** any authenticated user uploads a rubric PDF source type
- **THEN** the system SHALL reject the request with a clear validation error

#### Scenario: Faculty uploads an SLM
- **WHEN** an authenticated faculty user uploads an SLM
- **THEN** the system SHALL accept only the SLM workflow

#### Scenario: Faculty attempts curriculum upload
- **WHEN** an authenticated faculty user uploads a curriculum document
- **THEN** the system SHALL deny the request without granting institutional-ingestion permissions

#### Scenario: Admin uploads an active institutional document
- **WHEN** an authenticated admin uploads a syllabus, supported-program curriculum, or policy document through Admin Ingestion
- **THEN** the system SHALL process it in its source-appropriate local store
