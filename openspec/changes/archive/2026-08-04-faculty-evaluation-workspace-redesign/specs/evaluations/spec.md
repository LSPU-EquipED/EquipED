## ADDED Requirements

### Requirement: Evaluation activity is streamable via Server-Sent Events
The system SHALL expose a Server-Sent Events endpoint `GET /api/v1/evaluations/{id}/activity` that streams per-agent activity events for the active evaluation job. The endpoint SHALL require authentication and SHALL only stream events for jobs owned by the authenticated user. The stream SHALL replay a bounded per-job buffer of recent events before delivering live events, so a late-joining client receives the meaningful history.

#### Scenario: Authenticated owner subscribes to the activity stream
- **WHEN** the authenticated owner of an evaluation job opens the workspace for that job
- **THEN** the system SHALL accept the SSE subscription
- **AND** SHALL first replay the most recent N events from the per-job buffer
- **AND** SHALL then stream live events as they are emitted by the supervisor and the agents

#### Scenario: Non-owner attempts to subscribe
- **WHEN** an authenticated user attempts to subscribe to the activity stream for an evaluation job they do not own
- **THEN** the system SHALL deny the subscription
- **AND** SHALL NOT disclose the job's existence or activity

#### Scenario: Event categories match the existing log categories
- **WHEN** the supervisor or any agent emits a log line in one of the existing categories (`[EVAL_TIMING]`, `[SME_GROUPED]`, `[ENGINE_TIMING]`, `[EVAL_PROMPT_BUDGET]`, `[EVAL_PROMPT_SIZE]`)
- **THEN** the same call site SHALL also push a typed event into the per-job buffer
- **AND** the stdout log line SHALL continue to be emitted unchanged
- **AND** the SSE endpoint SHALL stream the typed event to subscribed clients with the schema `{job_id, ts, agent, category, stage, message, payload?}`

#### Scenario: Per-job buffer is bounded
- **WHEN** the per-job event buffer for an active evaluation reaches its retention bound (default 500 events)
- **THEN** the system SHALL drop the oldest events
- **AND** SHALL always retain a terminal lifecycle event (one of `COMPLETED`, `FAILED`, `COMPLETED_PARTIAL`) regardless of bound
- **AND** the buffer SHALL be evicted from memory one hour after the lifecycle reaches a terminal state

#### Scenario: Lifecycle stage transitions are emitted as events
- **WHEN** the evaluation lifecycle transitions between stages (`SUBMITTED` → `PREPROCESSING` → `EVALUATING` → `SYNTHESIZING` → terminal)
- **THEN** the system SHALL emit a `lifecycle` event into the per-job buffer
- **AND** the SSE endpoint SHALL stream the event to subscribed clients

#### Scenario: Heartbeat during parallel execution is also an event
- **WHEN** the system emits the `EVALUATING` heartbeat before dispatching agents to the thread pool
- **OR** the system emits the heartbeat after all agent futures complete
- **THEN** the heartbeat SHALL also be visible as a typed `eval_timing` event on the SSE stream
- **AND** the stdout log line SHALL continue to be emitted unchanged

#### Scenario: SSE connection emits a keepalive
- **WHEN** no event has been emitted for 15 seconds
- **THEN** the SSE endpoint SHALL emit a `: keepalive` comment on the stream
- **AND** the client SHALL treat the keepalive as a no-op (no UI change)

#### Scenario: Client disconnect is handled
- **WHEN** a subscribed client disconnects
- **THEN** the system SHALL remove the client from the per-job buffer's subscriber list
- **AND** the evaluation job SHALL continue to run unaffected
- **AND** a reconnecting client SHALL receive the buffer replay on reconnection
