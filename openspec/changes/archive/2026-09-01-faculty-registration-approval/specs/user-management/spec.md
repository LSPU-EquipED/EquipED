## ADDED Requirements

### Requirement: Admin account approval
The system MUST expose administrator-only account approval endpoints that transition verified faculty accounts between pending, approved, rejected, and suspended states. Approving an account SHALL activate the user, rejecting or suspending an account SHALL prevent authentication, and notification delivery failure SHALL NOT roll back committed status transitions.

#### Scenario: Admin approves pending faculty account
- **Given** an authenticated admin user
- **When** the admin submits an approval request for a pending faculty user
- **Then** the system updates the account status to approved, activates the user, and sends an approval notification email

#### Scenario: Admin rejects pending faculty account
- **Given** an authenticated admin user
- **When** the admin submits a rejection request for a pending faculty user
- **Then** the system updates the account status to rejected, ensures the user remains inactive, and dispatches a rejection notification email

#### Scenario: Admin suspends an approved faculty account
- **Given** an authenticated admin user
- **When** the admin submits a suspension request for an approved user
- **Then** the system updates the account status to suspended and deactivates the user

#### Scenario: Suspend and reapprove use approval lifecycle
- **Given** an authenticated admin user
- **When** the admin suspends an approved user or reapproves a suspended user
- **Then** the system transitions the account status through the approval lifecycle and synchronizes active status accordingly

#### Scenario: Status transition persists upon notification failure
- **Given** an authenticated admin user performing an approval or rejection
- **When** the account status update succeeds in the database but notification dispatch encounters an error
- **Then** the status change remains committed and the operation does not fail

#### Scenario: Notification failure logs bounded warning
- **Given** an authenticated admin user performing an approval or rejection
- **When** background notification delivery fails after status transition commits
- **Then** the system logs a bounded warning without rolling back or failing the admin action

#### Scenario: Admin UI exposes suspended state
- **Given** an authenticated admin viewing the faculty management interface
- **When** user accounts in suspended status are listed
- **Then** the interface explicitly identifies and labels the suspended account status

#### Scenario: Non-admin denied account approval actions
- **Given** an authenticated non-admin user
- **When** the user attempts to approve, reject, or suspend an account
- **Then** the system returns a 403 Forbidden response

### Requirement: Admin user mutations and response contracts
The system SHALL validate admin-created passwords against length bounds and return the complete allowlisted user response contract for admin user mutations.

#### Scenario: Admin-created user passwords enforce length bounds
- **Given** an authenticated admin creating or modifying a user password
- **When** the password length is less than 8 characters or exceeds 256 characters
- **Then** the system SHALL reject the mutation request with a validation error

#### Scenario: Admin user mutations return complete response schema
- **Given** an authenticated admin creating, updating, or changing the status of a user
- **When** the mutation succeeds
- **Then** the system SHALL return the full allowlisted `AdminUserResponse` payload
