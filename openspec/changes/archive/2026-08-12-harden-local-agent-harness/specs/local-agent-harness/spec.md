## ADDED Requirements

### Requirement: Local provider and deterministic fake runtime
The harness SHALL target local model alias `equiped-gemma3-4b-qat-q4` by default and SHALL support deterministic fake OpenAI-compatible providers without a Groq dependency.

#### Scenario: Offline harness run
- **WHEN** tests run with the fake provider
- **THEN** identical requests produce identical completions and runtime metadata without network access

### Requirement: Explicit structured output capability
The transport SHALL advertise JSON-object or JSON-Schema capability explicitly; schemas and semantic validation SHALL remain agent-local authoritative checks and the transport SHALL not silently downgrade.

#### Scenario: Unsupported schema mode
- **WHEN** a provider lacks the requested capability
- **THEN** the request fails explicitly without an implicit retry in another mode

### Requirement: Bounded completion and provider gate
The transport SHALL return immutable typed completion metadata and enforce one absolute monotonic deadline per logical LLM request across gate wait, attempts, backoff, and explicit distinct fallback. Implicit/global and same-target fallback SHALL be disabled. A process-wide provider/endpoint/model gate SHALL enforce configurable quotas, with quotas disabled for local providers.

#### Scenario: Deadline and attribution
- **WHEN** a gated request reaches its deadline or a distinct fallback serves it
- **THEN** it fails or records the actual served model with bounded usage, finish reason, timing, attempts, and allowlisted rate data

### Requirement: FIFO single-job admission and recovery
The system SHALL admit at most one evaluation globally using database-backed FIFO slot `1`, atomic CAS/token transitions, terminal release, one queue drainer, one worker, fresh heartbeats, and heartbeat-aware startup recovery without Redis/Celery.

#### Scenario: Queue advances safely
- **WHEN** the active job succeeds, fails, or is recovered as stale
- **THEN** its slot is released atomically and the oldest submitted job is claimed exactly once
