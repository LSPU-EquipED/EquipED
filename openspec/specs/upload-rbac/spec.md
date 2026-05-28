# upload-rbac Specification

## Purpose
Restricts institutional document uploads (syllabus, curriculum, rubric) to admin users only.
## Requirements
### Requirement: Restrict institutional document uploads to admins
The system MUST restrict ingestion of institutional knowledge base documents (source types `syllabus`, `curriculum`, `rubric`) to administrators only. Faculty users MUST NOT be able to upload documents with these source types.

#### Scenario: Faculty attempts restricted upload
- **Given** an authenticated user with the `faculty` role
- **When** they attempt to upload a file with source type `syllabus`, `curriculum`, or `rubric`
- **Then** the system rejects the upload and returns a 403 Forbidden with a clear error message

#### Scenario: Admin uploads institutional document
- **Given** an authenticated admin user
- **When** they upload a file with source type `syllabus`, `curriculum`, or `rubric`
- **Then** the system processes and embeds the document normally

