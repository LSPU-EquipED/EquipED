## ADDED Requirements

### Requirement: Official development topology
The project SHALL define one official development topology for the current phase: frontend local per developer, backend local per developer, shared Neon PostgreSQL for relational persistence, local Chroma per developer for vector storage, and local per-developer uploads.

#### Scenario: Team member follows the standard environment
- **WHEN** a developer sets up the project for normal feature work
- **THEN** the documented development environment SHALL direct them to run frontend and backend locally, use Neon for relational persistence, and use a local Chroma instance for vector storage

#### Scenario: Temporary dev database is described without changing target architecture
- **WHEN** the development database is described in project guidance
- **THEN** the system SHALL treat Neon as the current relational host for development and SHALL preserve future migration to localized LSPU-hosted PostgreSQL as the target architecture

### Requirement: Docker role is explicitly limited for this phase
The project SHALL define Docker as a local infrastructure helper for the current phase rather than the official full-stack application runtime.

#### Scenario: Developer reads how to run the stack
- **WHEN** a developer consults project guidance for starting the application
- **THEN** the guidance SHALL not present `docker compose up` alone as the canonical way to run the full frontend and backend application stack

#### Scenario: Scaffold app containers remain non-canonical
- **WHEN** server and client Docker assets are still scaffold placeholders without stable runtime commands
- **THEN** the documented workflow SHALL treat those containers as non-canonical for day-to-day app execution

### Requirement: Shared relational state and local vector state are distinguished
The project SHALL distinguish shared relational state from local vector state so developers do not assume a PostgreSQL record implies retrievability on every machine.

#### Scenario: Shared document metadata exists without local vectors
- **WHEN** a document row exists in the shared relational database but the local Chroma instance has not indexed that document
- **THEN** the workflow SHALL treat retrieval and evaluation on that machine as unavailable or non-authoritative until local vector state is built

#### Scenario: Developer evaluates locally ingested content
- **WHEN** a developer tests retrieval or evaluation behavior
- **THEN** the expected reliable path SHALL be documents and vectors ingested on that same machine unless the team explicitly standardizes a shared vector-state workflow later

### Requirement: Development configuration remains migration-safe
The development environment SHALL remain PostgreSQL-generic and local-deployment-friendly so the future move from Neon to LSPU-local infrastructure can be accomplished primarily through configuration and operational workflow changes.

#### Scenario: Database host changes for pre-production or deployment
- **WHEN** the team replaces Neon with localized PostgreSQL later
- **THEN** the environment contract SHALL allow `DATABASE_URL` and related operational setup to change without redefining the core development architecture

#### Scenario: Team revisits topology before retrieval-heavy collaboration
- **WHEN** multiple developers need consistent retrieval and evaluation behavior against the same document corpus
- **THEN** the team SHALL revisit the local-per-developer Chroma assumption before treating cross-machine evaluation results as equivalent
