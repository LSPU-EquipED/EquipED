## MODIFIED Requirements

### Requirement: Evaluation jobs progress into Layer 3
The system SHALL submit jobs through FIFO admission and execute Layer 3 with supervisor-managed ThreadPoolExecutor using immutable precomputed context and canonical clean source text prepared once. Per-agent routing SHALL preserve attribution and distinct aliases SHALL NOT imply independent quota pools.

#### Scenario: Shared context dispatch
- **WHEN** the admitted job enters Layer 3
- **THEN** canonical source and authorized rubric/reference context are prepared once and supplied read-only to parallel agents

### Requirement: Layer 4 synthesis and monitoring matrix updates
The system SHALL run deterministic Layer 4 synthesis as the terminal automated output. Explicit no-curriculum partial jobs SHALL complete honestly as `COMPLETED` with `COMPLETED_PARTIAL`; requested full jobs with missing curriculum or Coordinator failure SHALL terminate `FAILED` after available outputs are synthesized.

#### Scenario: Terminal synthesis
- **WHEN** Layer 3 persistence finishes
- **THEN** deterministic synthesis writes the matrix and no further automated layer runs

### Requirement: Evaluation lifecycle status sequence
Evaluation jobs SHALL use CAS/token transitions and heartbeat-aware recovery; each logical LLM request SHALL use the transport's absolute monotonic request deadline, and `EMBEDDING` SHALL NOT be used.

#### Scenario: Stale worker recovery
- **WHEN** a non-terminal heartbeat is stale
- **THEN** recovery claims or fails the job only through an ownership-safe CAS transition and drains the next FIFO job
