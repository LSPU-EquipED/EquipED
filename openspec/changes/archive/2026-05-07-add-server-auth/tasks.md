## 1. Auth module and schema foundations

- [x] 1.1 Create the dedicated `server/modules/auth/` module structure with router, service, models, schemas, and module-local exceptions
- [x] 1.2 Add shared SQLAlchemy base/metadata wiring so auth models can participate in Alembic autogeneration
- [x] 1.3 Extend the `users` schema for local credential storage and add a persisted `sessions` model for server-managed sessions

## 2. Migrations and bootstrap path

- [x] 2.1 Update Alembic environment configuration to load application metadata for auth models
- [x] 2.2 Generate and review the initial auth migration for user credential and session persistence changes
- [x] 2.3 Define and implement the backend-controlled first-admin bootstrap path without enabling public registration

## 3. Auth API implementation

- [x] 3.1 Implement password hashing and credential verification in the auth service
- [x] 3.2 Implement `POST /api/v1/auth/login` with active-user validation and session creation
- [x] 3.3 Implement `POST /api/v1/auth/logout` with session invalidation and cookie clearing
- [x] 3.4 Implement `GET /api/v1/auth/me` returning authenticated user identity and role context

## 4. Integration and verification

- [x] 4.1 Mount the auth router in `server/main.py` under `/api/v1/auth`
- [x] 4.2 Add backend tests covering successful login, rejected login, current-session lookup, and logout
- [x] 4.3 Update backend docs/config examples to describe the auth contract, cookie/session behavior, and bootstrap expectations
