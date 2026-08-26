## Context

EquipED has completed its backend infrastructure setup, including FastAPI app bootstrapping, SQLAlchemy/Alembic wiring, and a Neon-backed PostgreSQL environment, but it still lacks any server-side authentication capability. The client already assumes an authenticated current-user shape with role-based access control, while the TDD currently defines a `users` table without password material, a session-based Phase 1 auth decision, and no dedicated backend auth module.

This change is server-only. Frontend login forms, auth hooks, and route-state wiring are intentionally deferred because another contributor is handling the client integration. The backend must therefore expose a stable, frontend-agnostic auth contract that can be wired later without redesigning server behavior.

## Goals / Non-Goals

**Goals:**
- Introduce a dedicated backend auth module that fits the modular monolith structure.
- Support locally managed credentials for existing institutional users.
- Implement persisted, database-backed sessions for Phase 1 session authentication.
- Expose a minimal auth API contract for login, logout, and current-session lookup.
- Define a safe bootstrap path for the first administrative user.

**Non-Goals:**
- No frontend auth implementation or UI wiring.
- No self-service registration, password reset, or email verification flows.
- No external identity providers or JWT-based auth.
- No advanced security features such as MFA, device management, or audit dashboards in this change.

## Decisions

### 1. Add a dedicated `server/modules/auth/` module
Authentication is domain logic, not infrastructure, so it SHALL not live in `server/core/`. It also does not belong under `admin`, because all users require authentication while only admins require administration capabilities.

**Alternatives considered:**
- Put auth logic in `core/` → rejected because `core/` is infrastructure-only by repo guardrails.
- Put auth under `admin/` → rejected because it mixes identity with administration.

### 2. Extend `users` and add a persisted `sessions` table
The existing `users` table SHALL be extended with password storage fields rather than introducing a separate credentials table in Phase 1. A new `sessions` table SHALL store opaque server-issued sessions associated with users.

This keeps the first feature slice small while still making authentication real. It avoids over-modeling before there is proof the system needs separate identity/credential boundaries.

**Alternatives considered:**
- Separate `user_credentials` table → cleaner long-term boundary, but too much complexity for the first feature slice.
- Signed cookie with no session table → simpler runtime path, but weaker revocation/logout semantics and less aligned with the session-based decision.

### 3. Use DB-backed opaque cookie sessions
The server SHALL issue an opaque session token on successful login, persist a corresponding session record in PostgreSQL, and use an HTTP-only cookie as the transport mechanism. The cookie-based session model preserves the Phase 1 session-auth direction and keeps the frontend contract simple.

**Alternatives considered:**
- JWT in cookie or header → rejected because it drifts from the chosen Phase 1 session model.
- Stateless signed cookie only → rejected because explicit session persistence is more controllable for logout and revocation.

### 4. Limit the Phase 1 auth API to login, logout, and current user
The backend auth surface SHALL be limited to:
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`

This is sufficient to establish authenticated identity and role-aware current-user context without pulling in adjacent user-management features too early.

**Alternatives considered:**
- Add registration or password reset now → rejected as unnecessary expansion.
- Add admin user-management endpoints in the same change → deferred to a later capability.

### 5. Bootstrap the first admin without self-registration
The system SHALL support an initial administrative-user bootstrap path that does not require open registration. The preferred direction is a controlled bootstrap mechanism suitable for local development and early deployments, with a path to later replace it with admin-managed user creation.

**Alternatives considered:**
- Open self-registration → rejected because the platform is institutional and role-sensitive.
- Manual DB-only bootstrap forever → workable short-term but too operationally awkward to be the only path.

## Risks / Trade-offs

- **[Spec drift between TDD and implementation]** → Capture auth as a formal OpenSpec capability before implementation, then update TDD/API docs as part of the change.
- **[Bootstrap path becoming a security footgun]** → Keep the bootstrap mechanism narrow, explicit, and easy to remove or disable after initial setup.
- **[Cross-origin cookie surprises during frontend integration]** → Define cookie and credential behavior clearly in the API contract so the frontend can wire `credentials: include` correctly later.
- **[Auth scope expanding into a full identity platform]** → Keep this change limited to login/logout/me plus schema/session foundations.
