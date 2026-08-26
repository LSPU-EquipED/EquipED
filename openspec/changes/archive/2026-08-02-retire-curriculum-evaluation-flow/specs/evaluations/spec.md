## ADDED Requirements

### Requirement: New curriculum-retired evaluations require confirmed partial context
When curriculum retirement is active, the system SHALL reject a new evaluation
unless it has explicit no-curriculum partial intent and a valid confirmed
program. It SHALL persist that confirmed program independently of detected SLM
metadata and SHALL exclude Coordinator before execution.

#### Scenario: Direct API caller bypasses setup
- **WHEN** a caller submits a new evaluation without confirmed program context or
  explicit partial intent
- **THEN** the system SHALL reject the request
