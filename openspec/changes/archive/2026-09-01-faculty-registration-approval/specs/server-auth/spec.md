## ADDED Requirements

### Requirement: Public faculty registration
The backend SHALL provide public faculty registration under `/api/v1/auth/registrations`. Registration SHALL require an `@lspu.edu.ph` institutional email, faculty identity fields, and a password, and SHALL verify email ownership via a time-limited one-time password (OTP) before creating a user account. Verified accounts SHALL be created inactive with `pending` approval status in local persistent storage and SHALL remain unable to authenticate until an administrator approves them. Existing administrative accounts SHALL be rejected from public registration, while eligible rejected faculty accounts MAY re-register and reset review metadata upon verification.

#### Scenario: Faculty submits valid registration details and receives OTP
- **WHEN** an unauthenticated faculty member submits valid `@lspu.edu.ph` registration fields
- **THEN** the system SHALL create a pending registration record and issue a time-limited OTP without creating an active user account

#### Scenario: Registration start rolls back on email delivery failure
- **WHEN** registration start or OTP resend encounters an email delivery failure
- **THEN** pending registration state changes SHALL roll back and no user account SHALL be created, allowing the user to retry

#### Scenario: Verified OTP creates inactive pending user account
- **WHEN** the user submits the correct OTP for their pending registration
- **THEN** the system SHALL mark registration verified and create a faculty user account with `pending` status and `is_active=false`

#### Scenario: Concurrent OTP verification enforces attempt limits atomically
- **WHEN** concurrent verification requests are submitted against a pending registration
- **THEN** attempt counts SHALL update atomically and reject requests exceeding the maximum verification attempts

#### Scenario: Registration rejected for non-institutional email domain
- **WHEN** a user attempts registration with an email domain other than `@lspu.edu.ph`
- **THEN** the backend SHALL reject the registration request

#### Scenario: Public registration rejects existing admin accounts
- **WHEN** a public registration request provides an email belonging to an existing administrative account
- **THEN** the backend SHALL reject the registration request

#### Scenario: Eligible rejected faculty can re-register and clear review metadata
- **WHEN** a faculty member with a rejected account submits valid registration details and verifies OTP
- **THEN** the backend SHALL reset the account status to `pending`, keep `is_active=false`, and clear previous review metadata

#### Scenario: Unapproved pending user cannot authenticate
- **WHEN** a faculty member with `pending` status attempts to log in
- **THEN** the system SHALL reject the login attempt

### Requirement: Public authentication rate limiting
The backend SHALL enforce bounded process-local per-IP and per-identity rate limiting across public authentication and registration endpoints, returning HTTP 429 and retry timing headers when limits are exceeded.

#### Scenario: Rate limits enforced on public auth endpoints
- **WHEN** a client exceeds rate limits for login, registration start, verification, or resend requests
- **THEN** the system SHALL reject the request with HTTP 429 and a `Retry-After` header

#### Scenario: Registration start cannot bypass resend cooldown
- **WHEN** a registration start request is submitted while an active OTP cooldown is in progress for that identity
- **THEN** the system SHALL reject the request with HTTP 429 and retry timing headers

### Requirement: Account approval notifications
The backend SHALL send notification emails to the registered LSPU address for OTP issuance and after an administrator approves or rejects the account. Email provider credentials and configuration SHALL remain strictly server-side and adhere to institutional data residency, and an approval or rejection action SHALL remain committed in the database even if notification delivery fails. Admin notifications SHALL execute post-commit via bounded in-process background tasks.

#### Scenario: OTP verification email dispatched
- **WHEN** a valid faculty registration request is initiated or an OTP resend is requested
- **THEN** the system SHALL send an email containing the time-limited OTP to the registered LSPU email address

#### Scenario: Status notification dispatched upon admin decision
- **WHEN** an administrator approves or rejects a pending faculty account
- **THEN** the system SHALL send an account status notification email to the user's institutional email address

#### Scenario: Status transition persists upon notification delivery failure
- **WHEN** an administrator approval or rejection action commits in the database but the email provider fails to deliver the notification
- **THEN** the account status update SHALL remain committed in the database and not be rolled back

#### Scenario: Admin status notification dispatched in bounded background execution
- **WHEN** an administrator commits an account approval or rejection
- **THEN** the notification SHALL be dispatched in the background without blocking the mutation response or transaction commit

### Requirement: Server environment startup safety
The backend SHALL validate runtime configuration invariants upon startup and fail closed if insecure email, cookie, URL, or SMTP configurations are detected outside development mode.

#### Scenario: Non-development startup fails closed on insecure configuration
- **WHEN** the backend initializes in a non-development environment with console email delivery, non-HTTPS public application URL, insecure session cookies, or insecure SMTP transport
- **THEN** the application startup SHALL abort with an explicit configuration error

### Requirement: Session revocation on status change
The backend SHALL revoke active sessions whenever an account leaves the approved state, and subsequent reapproval SHALL NOT revive previously invalidated sessions.

#### Scenario: Leaving approved state revokes active sessions
- **WHEN** an approved faculty user's account status transitions to rejected or suspended
- **THEN** the system SHALL invalidate all existing active sessions for that user

#### Scenario: Reapproval does not revive invalidated sessions
- **WHEN** a previously suspended or rejected user is reapproved by an administrator
- **THEN** previously revoked sessions SHALL remain invalid and require a new login

## MODIFIED Requirements

### Requirement: Initial admin bootstrap
The backend SHALL provide a controlled path to establish the first administrative user without enabling open self-registration.

#### Scenario: First admin can be provisioned without public registration
- **WHEN** the system is initialized for first use
- **THEN** there SHALL be a documented backend-controlled way to create the first admin account

#### Scenario: Public registration is unavailable
- **WHEN** an unauthenticated user attempts direct administrative creation or open self-service registration
- **THEN** the backend SHALL not expose uncontrolled admin creation outside the controlled faculty registration and approval flow
