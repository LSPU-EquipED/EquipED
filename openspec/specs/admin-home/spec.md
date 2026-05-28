# admin-home Specification

## Purpose
Admin dashboard landing page with summary cards, quick action buttons, and a recent activity feed.
## Requirements
### Requirement: Admin summary cards
The admin home page at `/admin` MUST display summary cards showing: Total SLMs Processed, Active Evaluation Jobs, and Registered Faculty counts.

#### Scenario: Admin views summary
- **Given** an authenticated administrator
- **When** they navigate to `/admin`
- **Then** they see summary cards displaying the current counts for documents, active evaluation jobs, and registered faculty fetched from the backend summary API

### Requirement: Admin quick action buttons
The admin home page MUST provide "Quick Action" buttons for creating a faculty account and uploading a reference document.

#### Scenario: Admin uses quick actions
- **Given** an authenticated administrator on the `/admin` page
- **When** they click a "Quick Action" button
- **Then** they are navigated to the corresponding action page (create faculty account or upload reference document)

### Requirement: Recent activity feed
The admin home page MUST display a "Recent Activity" feed showing a summarized matrix view of recent system activity.

#### Scenario: Admin views recent activity
- **Given** an authenticated administrator on the `/admin` page
- **When** the page loads
- **Then** they see a recent activity feed with summarized entries from the system matrix

