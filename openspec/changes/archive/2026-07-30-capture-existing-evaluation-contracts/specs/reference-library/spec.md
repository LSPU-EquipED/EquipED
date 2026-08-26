## ADDED Requirements

### Requirement: Curriculum references use the curriculum extraction contract
Before embedding a curriculum reference, the system SHALL process it through the `curriculum-reference-extraction` contract. Curriculum-specific extraction SHALL determine chunk semantics; the Reference Library SHALL continue to own reference lifecycle, health, access, preview, deletion, and embedding rebuild behavior.

#### Scenario: Admin ingests a curriculum reference
- **WHEN** an admin uploads a curriculum reference
- **THEN** the system SHALL apply the curriculum extraction contract before persisting chunks and creating reference embeddings

#### Scenario: Curriculum-specific extraction finds no specialized layout
- **WHEN** the curriculum extraction contract falls back to generic page chunking
- **THEN** the Reference Library SHALL persist and manage the resulting curriculum chunks through its existing lifecycle rules
