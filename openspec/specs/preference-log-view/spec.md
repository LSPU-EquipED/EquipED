# Preference Log View Capability

## Purpose

Expose an administrative view of human feedback (Accept/Reject/Edit audits) to help admins understand how well the system's evaluations align with expert expectations.

## Requirements

### Requirement: Preference logs are tracked and queryable
The system SHALL maintain a `PreferenceLog` model in the `feedback` module with fields: `log_id` (UUID, primary key), `evaluation_id` (UUID, foreign key), `user_id` (UUID, foreign key), `action` (String), `edited_json` (JSON, optional), `notes` (Text, optional), `created_at` (DateTime).

#### Scenario: Admin views preference logs
- **WHEN** an admin calls `GET /admin/preferences`
- **THEN** the system SHALL return a paginated list of preference logs, ordered by newest first

### Requirement: Preference logs are filterable
The system SHALL support filtering by `action` with valid values: `ACCEPT`, `REJECT`, `EDIT`.

#### Scenario: Filtering by action
- **WHEN** an admin filters by `action=REJECT`
- **THEN** the system SHALL return only preference logs with action `REJECT`

### Requirement: Preference log endpoint enforces admin access
The system SHALL restrict `GET /admin/preferences` to users with the `admin` role.

#### Scenario: Non-admin access denied
- **WHEN** a non-admin user accesses `GET /admin/preferences`
- **THEN** the system SHALL return `403 Forbidden`
