# Design

- `PendingRegistration` stores an opaque-token hash, password hash, OTP hash, expiration, attempt count, and required faculty profile fields. No user row is created until OTP verification succeeds.
- Verified registrations create or update a faculty `User` with `account_status=pending` and `is_active=false`.
- Public registration rejects existing admin accounts. Eligible rejected faculty accounts can re-register, which resets `account_status` to `pending`, sets `is_active=false`, and clears stale review metadata (`reviewed_by_id`, `reviewed_at`, `rejection_reason`).
- Public endpoints (`/login`, `/registrations/start`, `/registrations/verify`, `/registrations/resend`) enforce bounded process-local per-IP and per-identity/token rate limits with `429 Too Many Requests` and `Retry-After` headers. Registration start enforces resend cooldowns to prevent bypass.
- Registration start and resend execute state changes and OTP email delivery synchronously and atomically; delivery failure rolls back the new pending state or OTP to permit immediate retry.
- OTP verification uses atomic updates and row-locking on `PendingRegistration` to ensure maximum attempt thresholds cannot be exceeded by concurrent requests.
- Admin approval sets `approved` and activates the account; rejection and suspension deactivate the user and revoke all active sessions. Reapproval requires fresh authentication and cannot revive old sessions.
- Admin UI explicitly exposes and labels `suspended` status. Account suspension and reapproval operate through the approval lifecycle rather than unmanaged boolean toggles.
- Admin-created and updated passwords enforce bounds of 8 to 256 characters. Admin user mutation responses return the full allowlisted `AdminUserResponse` schema.
- Admin approval/rejection notifications are dispatched post-commit via bounded in-process background execution (`BackgroundTasks`). Delivery errors do not roll back the status transition and are logged as bounded warnings.
- Email delivery is isolated behind `server.modules.auth.email`, supporting console delivery for development and Resend or STARTTLS SMTP for production. Non-development startup fails closed if console email, insecure session cookies, non-HTTPS public URLs, or insecure SMTP configurations are present.
- Migration 0002 uses SQLite-compatible batch operations (`batch_alter_table`) while preserving PostgreSQL compatibility. Existing managed users default to `approved` for backward compatibility.
