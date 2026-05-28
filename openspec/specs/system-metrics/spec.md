# system-metrics Specification

## Purpose
Admin summary endpoint returning system performance and data volume metrics for monitoring.
## Requirements
### Requirement: Admin summary metrics endpoint
The system MUST expose `GET /admin/summary` that returns high-level system performance and data volume metrics for administrative monitoring.

#### Scenario: Dashboard metrics fetch
- **Given** an authenticated admin user
- **When** they request `GET /admin/summary`
- **Then** the system returns a 200 response containing:
  - `total_documents`: count of all processed documents
  - `total_faculty`: count of all active faculty accounts
  - `active_evaluations`: count of evaluation jobs not in terminal states
  - `failed_evaluations`: count of all failed evaluation jobs

#### Scenario: Non-admin denied access
- **Given** an authenticated non-admin user
- **When** they request `GET /admin/summary`
- **Then** the system returns a 403 Forbidden response

