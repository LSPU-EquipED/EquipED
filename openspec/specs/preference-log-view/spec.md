# Preference Log View Capability

## Purpose

Expose an administrative view of human feedback (Accept/Reject/Edit audits) to help admins understand how well the system's evaluations align with expert expectations.

## Requirements

### Requirement: Preference logs are tracked and queryable
The system SHALL maintain a `PreferenceLog` model in the `feedback` module with fields: `log_id` (UUID, primary key), `evaluation_id` (UUID, foreign key), `user_id` (UUID, foreign key), `action` (String), `edited_json` (JSON, optional), `notes` (Text, optional), `created_at` (DateTime).

#### Scenario: Admin views preference logs
- **WHEN** an admin calls `GET /admin/preferences`
- **THEN** the system SHALL return a paginated response containing `items` (array of log entries), `total` (integer count of all matching logs), `page` (current page number), and `page_size` (items per page), ordered by newest first

#### Scenario: Pagination parameters
- **WHEN** an admin calls `GET /admin/preferences?page=2&page_size=10`
- **THEN** the system SHALL return the second page of up to 10 items with `page == 2`, `page_size == 10`, and `total` reflecting the full unpaginated count

### Requirement: Preference logs are filterable
The system SHALL support filtering by `action` via a query parameter with valid values: `ACCEPT`, `REJECT`, `EDIT`. Multiple filters SHALL be combined with AND logic when other query parameters (e.g. date range) are added in the future.

#### Scenario: Filtering by action
- **WHEN** an admin calls `GET /admin/preferences?action=REJECT`
- **THEN** the system SHALL return only preference logs with action `REJECT`, with pagination fields reflecting the filtered count

#### Scenario: No action filter returns all logs
- **WHEN** an admin calls `GET /admin/preferences` without an `action` parameter
- **THEN** the system SHALL return all preference logs across all actions

### Requirement: Preference log endpoint enforces admin access
The system SHALL restrict all `GET /admin/preferences` requests to authenticated users with the `admin` role. Unauthenticated requests SHALL receive `401 Unauthorized`; authenticated non-admin requests SHALL receive `403 Forbidden`.

#### Scenario: Non-admin access denied
- **WHEN** an authenticated non-admin user accesses `GET /admin/preferences`
- **THEN** the system SHALL return `403 Forbidden`

#### Scenario: Unauthenticated access denied
- **WHEN** an unauthenticated request accesses `GET /admin/preferences`
- **THEN** the system SHALL return `401 Unauthorized`
