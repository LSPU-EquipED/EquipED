## Purpose

Define how agent prompt definitions are stored, selected, and maintained for evaluation workflows.

## Requirements

### Requirement: Prompt definitions are centrally managed
The system SHALL keep agent prompts in a dedicated prompt management contract instead of embedding them directly in workflow code.

#### Scenario: Prompt content is sourced by role
- **WHEN** the evaluation workflow needs a prompt for a specific agent role
- **THEN** the system SHALL retrieve the matching managed prompt definition

### Requirement: Prompt selection is deterministic
The system SHALL resolve a single active prompt version for each supported agent role.

#### Scenario: Active prompt is loaded
- **WHEN** an agent role requests its prompt
- **THEN** the system SHALL return the active prompt version for that role

### Requirement: Prompt updates preserve workflow stability
The system SHALL allow prompt changes without altering the evaluation contract or requiring application code changes.

#### Scenario: Updated prompt is used on the next run
- **WHEN** a prompt definition is updated
- **THEN** the next evaluation run SHALL use the updated managed prompt

### Requirement: Prompt versions are managed via admin API
The system SHALL expose endpoints for administrators to list, create, and revert agent prompt versions.

#### Scenario: Listing prompt version history
- **WHEN** an admin requests `GET /admin/prompts/{agent_id}`
- **THEN** the system SHALL return all historical versions sorted newest first, each containing `version_id`, `version_number`, `prompt_text`, `is_active`, `updated_by`, and `created_at`

#### Scenario: Creating a new prompt version
- **WHEN** an admin submits a new `prompt_text` and optional `motivation`
- **THEN** the system SHALL create a new version with an incremented `version_number` and set all other versions for that agent to `is_active=False`

#### Scenario: Reverting to an older prompt version
- **WHEN** an admin calls `POST /admin/prompts/{agent_id}/revert/{version_id}`
- **THEN** the system SHALL clone the older version's text into a new active version and mark the previous active version as inactive

#### Scenario: Invalid agent or version
- **WHEN** a request targets an unknown `agent_id` or nonexistent `version_id`
- **THEN** the system SHALL return `404 Not Found`

### Requirement: Admin endpoints enforce role-based access
The system SHALL restrict all prompt management endpoints to users with the `admin` role.

#### Scenario: Non-admin access denied
- **WHEN** a non-admin user accesses any `/admin/prompts/` endpoint
- **THEN** the system SHALL return `403 Forbidden`

#### Scenario: Empty prompt text rejected
- **WHEN** an admin attempts to create a prompt with empty `prompt_text`
- **THEN** the system SHALL return `422 Unprocessable Entity`


### Requirement: Prompt attribution reflects consumed managed text
The system SHALL persist a prompt ID only when the exact managed prompt text affects outbound model input. SME SHALL use a new extraction-only managed preamble for grouped and criterion-fallback calls; historical prompt migrations SHALL remain immutable. Coordinator SHALL remain non-consuming and persist no prompt ID until a compatible fact-only prompt contract is separately added.

#### Scenario: Unconsumed Coordinator prompt
- **WHEN** Coordinator runs without a compatible managed fact-only contract
- **THEN** it sends no managed prompt and persists no prompt ID

#### Scenario: SME forward migration
- **WHEN** the SME extraction preamble is seeded
- **THEN** a new forward migration creates it without changing historical prompt rows
