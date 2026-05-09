# client-session-auth Specification

## Purpose
TBD - created by archiving change integrate-auth-and-documents-client-flow. Update Purpose after archive.
## Requirements
### Requirement: Web client provides a public login entry route
The web client SHALL provide a public route for unauthenticated users to access a login form for the existing server authentication module.

#### Scenario: Unauthenticated user opens the app
- **WHEN** a user reaches a protected client route without an authenticated session
- **THEN** the client routes the user to a public login entry page instead of rendering protected content

#### Scenario: Login form collects server-supported credentials
- **WHEN** the login page is rendered
- **THEN** the client presents inputs for email and password and a submit action that targets the existing server auth flow

### Requirement: Web client authenticates using server-managed session cookies
The web client SHALL authenticate against `/api/v1/auth/login` and maintain authenticated state through the server-managed session cookie.

#### Scenario: Successful login establishes client auth state
- **WHEN** the user submits valid credentials to the login action
- **THEN** the client sends the request with browser credential support, accepts the session cookie, and transitions to authenticated app state

#### Scenario: Invalid login remains on the login page
- **WHEN** the server rejects submitted credentials
- **THEN** the client remains on the login page and displays an authentication failure state without treating the response as success

### Requirement: Web client hydrates identity from the current-session endpoint
The web client SHALL call `/api/v1/auth/me` during authenticated app bootstrap and use the response as the source of truth for user identity and role context.

#### Scenario: Browser refresh preserves session-backed auth state
- **WHEN** an authenticated user refreshes the page
- **THEN** the client calls `/api/v1/auth/me` with browser credentials and restores authenticated identity from the server response

#### Scenario: Anonymous bootstrap resolves cleanly
- **WHEN** the app boots without a valid active session
- **THEN** the client resolves to anonymous state and does not treat the missing session as a fatal application error

### Requirement: Web client supports explicit logout
The web client SHALL terminate the authenticated browser session through the existing server logout endpoint.

#### Scenario: User logs out from an authenticated screen
- **WHEN** the user triggers logout
- **THEN** the client calls `/api/v1/auth/logout`, clears client auth state, and routes the user back to the public login entry page

### Requirement: Web client enforces role-aware route access from backend identity
The web client SHALL derive protected-route access from the hydrated backend user role rather than from locally invented role state.

#### Scenario: Role-gated route checks hydrated session role
- **WHEN** the client evaluates access to a role-protected route
- **THEN** the route check uses the current authenticated user role from `/api/v1/auth/me`

