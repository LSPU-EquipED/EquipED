## Purpose

Establish server-side authentication and session management for the EquipED backend using local credentials and persisted sessions.

## Requirements

### Requirement: Server authentication module
The backend SHALL provide a dedicated authentication module under the modular monolith for server-side identity and session handling.

#### Scenario: Auth module exposes versioned routes
- **WHEN** the FastAPI application starts
- **THEN** it SHALL mount authentication routes under `/api/v1/auth`

#### Scenario: Auth logic remains outside core infrastructure
- **WHEN** authentication behavior is implemented
- **THEN** credential validation and session lifecycle logic SHALL live in a dedicated auth module rather than `server/core/`

### Requirement: Local credential-based login
The backend SHALL authenticate locally managed users using email and password credentials stored in the relational database.

#### Scenario: Successful login for active user
- **WHEN** a request provides a valid email and password for an active user
- **THEN** the system SHALL create a new authenticated session and return a success response

#### Scenario: Login rejected for invalid credentials
- **WHEN** a request provides an unknown email or invalid password
- **THEN** the system SHALL reject the login attempt without disclosing which field was incorrect

#### Scenario: Login rejected for inactive user
- **WHEN** a request provides valid credentials for a user marked inactive
- **THEN** the system SHALL reject the login attempt

### Requirement: Persisted session-based authentication
The backend SHALL use persisted server-managed sessions for Phase 1 authentication, including browser-based clients.

#### Scenario: Session is persisted on login
- **WHEN** a user successfully logs in
- **THEN** the system SHALL create a session record associated with that user in PostgreSQL

#### Scenario: Session is transported by cookie
- **WHEN** a login succeeds
- **THEN** the system SHALL issue an HTTP-only session cookie representing the authenticated session

#### Scenario: Browser session can be reused on later authenticated requests
- **WHEN** a browser client sends a later request with the valid session cookie
- **THEN** the backend resolves it against the active persisted session instead of requiring re-authentication credentials

#### Scenario: Logout invalidates session
- **WHEN** an authenticated user calls the logout endpoint
- **THEN** the system SHALL invalidate the current session and clear the session cookie

### Requirement: Current user session lookup
The backend SHALL expose a current-session endpoint that returns the authenticated user identity and role context needed by downstream clients.

#### Scenario: Authenticated current user lookup
- **WHEN** a request presents a valid active session
- **THEN** the system SHALL return the authenticated user's identifier, display name, email, and role

#### Scenario: Anonymous current user lookup
- **WHEN** a request does not present a valid active session
- **THEN** the system SHALL return an unauthenticated result without treating the request as a server error

### Requirement: Initial admin bootstrap
The backend SHALL provide a controlled path to establish the first administrative user without enabling open self-registration.

#### Scenario: First admin can be provisioned without public registration
- **WHEN** the system is initialized for first use
- **THEN** there SHALL be a documented backend-controlled way to create the first admin account

#### Scenario: Public registration is unavailable
- **WHEN** an unauthenticated user interacts with the authentication API
- **THEN** the backend SHALL not expose open self-service account registration
