## ADDED Requirements

### Requirement: Processed faculty upload opens evaluation setup
After a faculty SLM upload succeeds with `PROCESSED` status, the client SHALL
invalidate document inventory state and navigate exactly once to that document's
evaluation route. The evaluation route SHALL resolve an existing job or render
setup and SHALL NOT auto-submit an evaluation.

#### Scenario: Faculty upload succeeds
- **WHEN** the faculty upload response is processed successfully
- **THEN** the client SHALL navigate to `/documents/{documentId}/evaluation`

#### Scenario: Faculty upload fails
- **WHEN** the upload fails or returns a non-processed result
- **THEN** the client SHALL remain on the upload experience and SHALL NOT
  navigate to evaluation
