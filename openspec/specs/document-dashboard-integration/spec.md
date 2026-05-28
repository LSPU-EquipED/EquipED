# document-dashboard-integration Specification

## Purpose
Connects the web client dashboard to authenticated backend APIs for document listing, upload, and processing status.
## Requirements
### Requirement: Dashboard lists documents from the authenticated backend API
The web client dashboard SHALL retrieve its document inventory from the existing authenticated documents API instead of local mock data.

#### Scenario: Authenticated dashboard load
- **WHEN** an authenticated user opens the dashboard
- **THEN** the client requests `GET /api/v1/documents` with browser credentials and renders the returned document list

#### Scenario: Dashboard handles empty inventory
- **WHEN** the authenticated documents API returns no documents
- **THEN** the dashboard renders an empty-state experience instead of mock rows

### Requirement: Dashboard reflects current backend document processing state
The dashboard SHALL map document processing information from the backend response into user-visible status indicators without inventing evaluation-complete output.

#### Scenario: Backend returns in-progress or processed document state
- **WHEN** the document list includes processing state fields from the backend
- **THEN** the dashboard renders corresponding status indicators based on those backend values

#### Scenario: Dashboard does not imply evaluation completion
- **WHEN** a document has been uploaded or processed but no evaluation contract exists yet
- **THEN** the dashboard does not present the document as having a completed evaluation report or final score

### Requirement: Web client uploads documents through the existing documents module
The web client SHALL submit new documents to the existing authenticated upload route using multipart form data that matches the backend request contract.

#### Scenario: User uploads a supported document successfully
- **WHEN** an authenticated user submits the upload form with a valid PDF and required metadata
- **THEN** the client sends a multipart request to `POST /api/v1/documents/upload` with browser credentials and receives the created document response

#### Scenario: Upload validation failure is surfaced to the user
- **WHEN** the backend rejects the upload request because of invalid or missing fields
- **THEN** the client displays an upload failure state based on the backend response instead of treating the upload as successful

### Requirement: Dashboard refreshes after successful upload
The web client SHALL update document inventory after a successful upload so the newly created document becomes visible in the dashboard flow.

#### Scenario: Successful upload returns to document inventory
- **WHEN** the upload request succeeds
- **THEN** the client refreshes or invalidates the dashboard document list and makes the new document discoverable in the authenticated UI

