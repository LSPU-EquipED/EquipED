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
