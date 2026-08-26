## Why

Phase 1 authentication has been decided as session-based, but the backend still has no authentication module, no credential storage, no session persistence, and no auth API contract. This blocks the first real server-side feature slice and leaves the frontend auth shell without a trustworthy backend identity source.

## What Changes

- Add a dedicated server-side authentication module for login, logout, and current-session lookup.
- Extend the backend data model to support locally managed user credentials and persisted sessions.
- Define the Phase 1 backend auth API contract for session-based authentication that the frontend can wire up later.
- Add migration coverage for auth-related tables and schema changes so the feature can run against the Neon-backed PostgreSQL environment.
- Document the bootstrap path for the first administrative user without introducing self-registration.

## Capabilities

### New Capabilities
- `server-auth`: Server-side authentication for locally managed users using persisted sessions and role-aware current-user retrieval.

### Modified Capabilities

## Impact

- Affected backend code under `server/`, especially a new `server/modules/auth/` module, Alembic metadata wiring, and database models.
- Adds auth endpoints under `/api/v1/auth/*`.
- Adds credential hashing and server-managed session persistence to the relational database layer.
- Establishes the backend auth contract that the client can integrate later without requiring frontend implementation in this change.
