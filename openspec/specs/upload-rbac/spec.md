# upload-rbac Specification

## Purpose
Restricts institutional document uploads (syllabus, curriculum, rubric) to admin users only and clarifies shared access for syllabus/curriculum references.
## Requirements
### Requirement: Restrict institutional document uploads to admins
The system MUST restrict ingestion of institutional knowledge base documents (source types `syllabus`, `curriculum`, `rubric`) to administrators only. Faculty users MUST NOT be able to upload documents with these source types. Admin-uploaded `syllabus` and `curriculum` documents SHALL become institution-shared references for authenticated read/use. Rubric documents SHALL remain managed through their separate rubric workflow and SHALL NOT be part of the Reference Library.

#### Scenario: Faculty attempts restricted upload
- **Given** an authenticated user with the `faculty` role
- **When** they attempt to upload a file with source type `syllabus`, `curriculum`, or `rubric`
- **Then** the system rejects the upload and returns a 403 Forbidden with a clear error message

#### Scenario: Admin uploads institutional document
- **Given** an authenticated admin user
- **When** they upload a file with source type `syllabus`, `curriculum`, or `rubric`
- **Then** the system processes and embeds the document normally

#### Scenario: Admin-uploaded references are shared
- **Given** an authenticated admin user uploaded a syllabus or curriculum document
- **When** an authenticated faculty user needs to read or use that syllabus or curriculum as an evaluation reference
- **Then** the system SHALL allow access without requiring the faculty user to own the reference document

#### Scenario: Faculty lists shared references
- **Given** syllabus or curriculum references exist in the document store
- **When** an authenticated faculty user lists documents filtered to syllabus or curriculum references
- **Then** the system SHALL include shared syllabus or curriculum references regardless of uploader
- **And** the system SHALL NOT include other users' SLM documents

#### Scenario: Reference management remains admin-only
- **Given** an uploaded syllabus or curriculum reference
- **When** an authenticated faculty user attempts to delete, rebuild, or otherwise manage the reference
- **Then** the system SHALL deny access
