## ADDED Requirements

### Requirement: Public registration and approval states
The web client SHALL provide public registration and OTP verification screens, followed by a waiting-for-admin-approval state. It SHALL provide clear approval and rejection messaging, including that approved users are notified by email, and SHALL not render protected application features for users whose backend account status is not approved.

#### Scenario: Unauthenticated user registers and verifies OTP
- **WHEN** an unauthenticated faculty member submits the registration form with valid LSPU details and submits the correct OTP
- **THEN** the client transitions to a waiting-for-approval view indicating the account is pending administrator review

#### Scenario: Pending account blocked from protected application access
- **WHEN** a user with pending account status attempts to navigate to protected client routes
- **THEN** the client prevents access to protected application features and displays a pending approval message

#### Scenario: Approved or rejected account messaging displayed
- **WHEN** a user views their registration or login status following an administrative decision
- **THEN** the client displays clear messaging indicating whether the account was approved or rejected and informs the user that approval notifications are delivered via email
