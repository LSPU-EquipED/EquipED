## MODIFIED Requirements

### Requirement: Evaluation setup requires program confirmation
The system SHALL require a faculty user to explicitly confirm or select an
allowed academic program before creating a new no-curriculum evaluation. A
detected program is a suggestion only and SHALL NOT substitute for confirmation.

#### Scenario: Detected program is shown
- **WHEN** evaluation setup opens for a processed SLM with detected metadata
- **THEN** the system SHALL show the detected program and require confirmation
  or replacement before partial submission

### Requirement: Fresh evaluation submission uses confirmed partial intent
The system SHALL submit every new faculty evaluation without a curriculum ID,
with explicit partial intent and persisted confirmed-program context. It SHALL
not offer curriculum selection, upload, or rebuild recovery actions.

#### Scenario: Faculty starts a new evaluation
- **WHEN** a faculty user confirms a program and acknowledges the partial warning
- **THEN** the system SHALL submit a no-curriculum partial evaluation with the
  confirmed program

## REMOVED Requirements

### Requirement: Curriculum suggestions are program-driven
**Reason**: Curriculum sources and selection are retired.
**Migration**: Use confirmed-program partial setup.

### Requirement: Curriculum suggestion preserves RAG retrieval
**Reason**: No new evaluation uses a curriculum reference.
**Migration**: Do not substitute syllabus as Coordinator evidence.

### Requirement: Admin curriculum references require program metadata
**Reason**: Curriculum ingestion is retired.
**Migration**: Retain program confirmation on the evaluation job instead.
