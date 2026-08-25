# program-confirmed-curriculum-selection Specification

## Purpose
Define the pre-evaluation setup flow that requires faculty to confirm the academic program and choose an explicit full or partial evaluation intent.

## Requirements

### Requirement: Evaluation setup requires program confirmation
The system SHALL require a faculty user to explicitly confirm or select an allowed academic program before creating a new full or partial evaluation. A detected program is a suggestion only and SHALL NOT substitute for confirmation. Curriculum suggestions SHALL refresh when confirmed program changes.

#### Scenario: Detected program is shown
- **WHEN** evaluation setup opens for a processed SLM with detected metadata
- **THEN** the system SHALL show the detected program and require confirmation or replacement before submission

#### Scenario: Confirmed program changes
- **WHEN** faculty changes the confirmed program between BSCS and BSInfoTech
- **THEN** the system SHALL clear any incompatible curriculum selection and load suggestions for the newly confirmed program

### Requirement: Faculty chooses explicit full or partial evaluation intent
After program confirmation, the system SHALL offer curriculum references matching that canonical program with readiness derived from the documents-owned readiness service. Faculty SHALL explicitly select one ready matching curriculum for full evaluation or explicitly select and acknowledge the no-curriculum partial fallback. The system SHALL NOT automatically select a preferred curriculum. Unready or mismatched curricula SHALL NOT be selectable.

#### Scenario: Faculty selects a ready matching curriculum
- **WHEN** a faculty user confirms a program and selects a ready curriculum for that program
- **THEN** the client SHALL submit the curriculum ID with full intent and confirmed program context

#### Scenario: Multiple ready curricula exist
- **WHEN** more than one ready curriculum matches the confirmed program
- **THEN** the client SHALL require an explicit faculty selection and SHALL NOT choose one automatically

#### Scenario: Faculty continues without curriculum
- **WHEN** a faculty user selects partial evaluation and acknowledges the no-curriculum warning
- **THEN** the client SHALL submit no curriculum ID, explicit partial intent, and confirmed program context

#### Scenario: Curriculum is unavailable
- **WHEN** matching curricula exist but are processing, failed, or missing local vectors
- **THEN** the client SHALL show their unavailable state and SHALL NOT allow them to be selected

#### Scenario: Intent is incomplete
- **WHEN** neither a ready curriculum nor an acknowledged partial fallback is selected
- **THEN** the client SHALL keep evaluation submission disabled
