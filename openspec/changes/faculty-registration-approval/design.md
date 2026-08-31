# Design

- `PendingRegistration` stores an opaque-token hash, password hash, OTP hash, expiration, attempt count, and required faculty profile fields. No user row is created until OTP verification succeeds.
- Verified registrations create or update a faculty `User` with `account_status=pending` and `is_active=false`.
- Admin approval sets `approved` and activates the account; rejection and suspension remain inaccessible. Status transitions revoke sessions when applicable.
- Email delivery is isolated behind `server.modules.auth.email`, with console delivery for development and Resend or STARTTLS SMTP for configured environments. Provider credentials never reach the client.
- Existing managed users default to `approved` in the migration for compatibility.
