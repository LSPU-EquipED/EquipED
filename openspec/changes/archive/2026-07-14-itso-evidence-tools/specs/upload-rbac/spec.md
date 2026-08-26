## MODIFIED Requirements

### Requirement: Restrict institutional document uploads to admins
The system MUST restrict ingestion of institutional knowledge base documents (source types `syllabus`, `curriculum`, `policy`, and `rubric`) to administrators only. Faculty users MUST NOT be able to upload documents with these source types. Admin-uploaded `syllabus` and `curriculum` documents SHALL become institution-shared references for authenticated read/use and preview. Policy documents SHALL be used internally by the ITSO evidence path for all authorized evaluations, including faculty-owned SLM evaluations, but SHALL NOT become faculty-visible shared references. Rubric documents SHALL remain managed through their separate rubric workflow and SHALL NOT be part of the Reference Library.

#### Scenario: Faculty attempts restricted upload
- **Given** an authenticated user with the `faculty` role
- **When** they attempt to upload a file with source type `syllabus`, `curriculum`, `policy`, or `rubric`
- **Then** the system rejects the upload and returns a 403 Forbidden with a clear error message

#### Scenario: Admin uploads institutional document
- **Given** an authenticated admin user
- **When** they upload a file with source type `syllabus`, `curriculum`, `policy`, or `rubric`
- **Then** the system processes and embeds the document in its source-appropriate local collection

#### Scenario: Admin-uploaded references are shared
- **Given** an authenticated admin user uploaded a syllabus or curriculum document
- **When** an authenticated faculty user needs to read or use that syllabus or curriculum as an evaluation reference
- **Then** the system SHALL allow access without requiring the faculty user to own the reference document

#### Scenario: Faculty lists shared references
- **Given** syllabus or curriculum references exist in the document store
- **When** an authenticated faculty user lists documents filtered to syllabus or curriculum references
- **Then** the system SHALL include shared syllabus or curriculum references regardless of uploader
- **And** the system SHALL NOT include policy documents or other users' SLM documents

#### Scenario: Policy management and access remain admin-only
- **Given** an uploaded policy reference
- **When** an authenticated faculty user attempts to list, fetch, preview, upload, rebuild, delete, or directly query that policy
- **Then** the system SHALL deny access without disclosing whether the policy exists

#### Scenario: Admin manages another admin's policy
- **Given** an uploaded policy reference created by one administrator
- **When** a different authenticated administrator manages that policy
- **Then** the system SHALL permit the action according to normal admin lifecycle controls
