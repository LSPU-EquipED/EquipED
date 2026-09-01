# Faculty registration and approval

## Why

Add controlled public faculty registration for LSPU users. Registration verifies ownership of the institutional email with an OTP, creates an inactive pending account, and gives administrators approval controls. OTP, approval, and rejection status are delivered by server-side email.

This reconciles the former “no public registration” auth contract with the approved faculty onboarding workflow. Admin bootstrap and all existing role/ownership rules remain unchanged.

## What Changes

- Add public faculty registration and OTP verification endpoints under `/api/v1/auth`.
- Add administrator approval, rejection, and suspension controls under `/admin/users`.
- Deliver OTP verification and account approval status notifications via server-side email.
- Add client registration and OTP verification screens and pending approval status messaging.

## Capabilities

### Modified Capabilities
- `client-session-auth`: Public registration and OTP verification screens, waiting-for-admin-approval state, and approval/rejection messaging.
- `server-auth`: Public faculty registration with OTP verification, approval notifications, and updated initial admin bootstrap.
- `user-management`: Admin account approval, rejection, and suspension endpoints and authorization controls.

## Impact

- Backend auth routes (`/api/v1/auth`) and user management endpoints (`/admin/users`).
- Client auth pages, registration forms, and route guards.
- Local data residency preserved: user credentials and pending registrations stored in local PostgreSQL.
