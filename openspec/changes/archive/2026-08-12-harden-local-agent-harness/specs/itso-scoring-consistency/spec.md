## MODIFIED Requirements

### Requirement: ITSO evidence is frozen and provenance is bounded
ITSO SHALL prepare one frozen task containing exact active criteria, packed evidence IDs/hashes, precheck and policy mode. Remote requests SHALL receive status-only policy evidence; policy content SHALL be local-only and never fall back externally. Only normalized output and bounded typed metadata SHALL persist; raw responses SHALL NOT persist.

#### Scenario: Policy locality
- **WHEN** policy evidence is disabled or a remote provider is selected
- **THEN** no policy clauses are delivered and local-only mode cannot fall back externally

### Requirement: ITSO consistency is regression-tested
ITSO SHALL validate an exact versioned criterion schema with no coercion, duplicates, unknown, empty, or incomplete criteria. It SHALL permit at most one whole-task regeneration from identical frozen context using bounded validator categories/paths.

#### Scenario: Invalid judgment
- **WHEN** output fails the exact schema
- **THEN** one safe regeneration occurs at most, then the result fails honestly without raw-output persistence
