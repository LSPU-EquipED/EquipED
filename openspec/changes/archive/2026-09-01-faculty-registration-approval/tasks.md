# Tasks

- [x] Add registration, OTP verification, and resend endpoints.
- [x] Add pending registration persistence and account approval fields.
- [x] Add server-side console/Resend email delivery and approval/rejection notifications.
- [x] Add Gmail-compatible STARTTLS SMTP delivery behind the email provider abstraction.
- [x] Add admin approval and rejection controls.
- [x] Add registration and OTP client screens and login link.
- [x] Update environment and setup documentation.
- [x] Add focused registration tests and run auth/admin verification.
- [x] Enforce bounded process-local rate limiting and Retry-After headers across public auth and registration endpoints (start, verify, resend, login).
- [x] Implement synchronous atomicity and rollback on OTP delivery failure for registration start and resend.
- [x] Add atomic attempt locking on pending registration verification to prevent concurrent attempt exhaustion bypass.
- [x] Restrict public registration to reject admin accounts, permit eligible rejected faculty re-registration, and clear stale review metadata.
- [x] Implement active session revocation when leaving approved status and prevent session revival on reapproval.
- [x] Add fail-closed startup validation for console email, session cookie security, public URL HTTPS, and SMTP settings in non-development environments.
- [x] Dispatch admin approval and rejection notifications post-commit via bounded background tasks with warning logging on failure.
- [x] Expose suspended state in the admin UI and unify suspension and reapproval under the account approval lifecycle.
- [x] Enforce 8..256 character admin-created password validation and return complete AdminUserResponse schemas on mutation endpoints.
- [x] Update migration 0002 to use SQLite-compatible batch operations while preserving PostgreSQL compatibility.
