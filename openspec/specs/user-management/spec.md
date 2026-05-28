# user-management Specification

## Purpose
Admin-only API endpoints for listing all registered users and creating new user accounts.
## Requirements
### Requirement: Admin user listing
The system MUST expose `GET /admin/users` that returns all registered users, accessible only to administrators.

#### Scenario: Admin lists users
- **Given** an authenticated admin user
- **When** they request `GET /admin/users`
- **Then** the system returns a 200 response with all registered users including their roles and status

### Requirement: Admin user creation
The system MUST expose `POST /admin/users` that creates a new user with a specified name, email, password, and role, accessible only to administrators.

#### Scenario: Admin creates a faculty account
- **Given** an authenticated admin user
- **When** they submit a POST request with name, email, password, and role
- **Then** the system hashes the password, persists the user, and returns the new user object with a 201 response

#### Scenario: Non-admin denied user creation
- **Given** an authenticated non-admin user
- **When** they request `POST /admin/users`
- **Then** the system returns a 403 Forbidden response

