# faculty-evaluation-workspace Specification

## Purpose

Define the faculty evaluation workspace — the centered, AI-product-like page that replaces the current two-pane evaluation view for the standard (Layer 3) evaluation. Covers the lifecycle timeline, the four subagent cards, the right contextual details panel with `Activity` / `Artifacts` / `Scorecard` tabs, the live activity stream, and the two-layer faculty sidebar (logo + nav, recent sessions). The two advisory features (curriculum alignment, syllabus alignment) are out of scope and keep their existing routes and pages. The admin dashboard is out of scope.

## ADDED Requirements

### Requirement: Lifecycle timeline is visible on the workspace
The workspace SHALL render a horizontal lifecycle timeline that reflects the evaluation job's current status. The stages are `SUBMITTED` → `PREPROCESSING` → `EVALUATING` → `SYNTHESIZING` → `COMPLETED | FAILED | COMPLETED_PARTIAL`, in that order. Each stage SHALL be visually distinct as pending (not yet reached), active (currently in), or complete (reached). The terminal stage SHALL remain visible after the lifecycle ends.

#### Scenario: Timeline reflects a running evaluation
- **WHEN** a faculty member opens the workspace for a job in `EVALUATING` state
- **THEN** the workspace SHALL render the timeline with `SUBMITTED`, `PREPROCESSING`, and `EVALUATING` shown as complete or active
- **AND** the remaining stages SHALL be shown as pending
- **AND** the timeline SHALL update live as the status changes

#### Scenario: Timeline shows a terminal failure
- **WHEN** a faculty member opens the workspace for a job in `FAILED` state
- **THEN** the timeline SHALL show all reached stages as complete
- **AND** SHALL show `FAILED` as the terminal stage with a distinct error color and a tooltip that links to the `Activity` tab

#### Scenario: Timeline shows a deliberate no-curriculum partial
- **WHEN** a faculty member opens the workspace for a job in `COMPLETED_PARTIAL` state
- **THEN** the timeline SHALL show all reached stages as complete
- **AND** SHALL show `COMPLETED_PARTIAL` as the terminal stage
- **AND** the `Scorecard` tab SHALL display a partial-acknowledgement chip explaining the no-curriculum cause

### Requirement: Four subagent cards appear on the EVALUATING stage
While the lifecycle is in the `EVALUATING` stage, the workspace SHALL render four subagent cards in a horizontal grid: SME, Coordinator, GAD, ITSO. Each card SHALL display the agent name, the configured model identifier, the current status (pending, running, done, failed), and the elapsed time. The cards SHALL be clickable; clicking a card SHALL open the right contextual details panel with the `Activity` tab focused on that agent's section.

#### Scenario: All four agents are pending before dispatch
- **WHEN** the workspace opens and the lifecycle has not yet entered `EVALUATING`
- **THEN** the four cards SHALL be visible
- **AND** each card SHALL show `pending` status with no elapsed time
- **AND** the cards SHALL be disabled (not clickable) until the agent has emitted at least one event

#### Scenario: One agent is running and another is done
- **WHEN** the SSE activity stream emits a `sme_grouped` event with `outcome=ok` for SME
- **AND** the Coordinator card has not yet emitted a terminal event
- **THEN** the SME card SHALL show `done` with the elapsed time from `EVALUATING`-entry to the terminal event
- **AND** the Coordinator card SHALL show `running` with the current elapsed time

#### Scenario: Agent card click opens the Activity tab focused on that agent
- **WHEN** a faculty member clicks the SME card
- **THEN** the right contextual details panel SHALL open
- **AND** the `Activity` tab SHALL be active
- **AND** the panel SHALL be scrolled to the SME section of the activity stream

#### Scenario: Failed agent card is visually distinct
- **WHEN** an agent emits an error event
- **THEN** the corresponding card SHALL show `failed` status with a distinct error color
- **AND** clicking the card SHALL open the `Activity` tab scrolled to the failure event

### Requirement: Right contextual details panel is collapsed by default
The right contextual details panel SHALL be collapsed by default (a thin segmented rail visible on the right edge of the canvas). The panel SHALL open in response to a click: agent card click opens the `Activity` tab; artifact row click opens the `Artifacts` tab; lifecycle completion SHALL default the panel to the `Scorecard` tab the first time the lifecycle reaches a terminal state in the current session.

#### Scenario: Panel is collapsed on initial render
- **WHEN** a faculty member opens the workspace for a fresh evaluation
- **THEN** the right panel SHALL be collapsed
- **AND** the segmented rail SHALL be visible

#### Scenario: Lifecycle reaches COMPLETED for the first time
- **WHEN** the lifecycle transitions to `COMPLETED` for the first time in the current session
- **THEN** the right panel SHALL open
- **AND** the `Scorecard` tab SHALL be active

#### Scenario: Lifecycle reaches FAILED for the first time
- **WHEN** the lifecycle transitions to `FAILED` for the first time in the current session
- **THEN** the right panel SHALL open
- **AND** the `Activity` tab SHALL be active so the user can see what failed

#### Scenario: User opens the Artifacts tab from a chunk citation
- **WHEN** a faculty member clicks a chunk citation in the scorecard or the activity stream
- **THEN** the right panel SHALL open
- **AND** the `Artifacts` tab SHALL be active
- **AND** the panel SHALL be scrolled to the cited chunk

### Requirement: Activity tab streams per-agent events via Server-Sent Events
The `Activity` tab SHALL display the live per-agent event stream for the active evaluation job. The events SHALL arrive via Server-Sent Events from `GET /api/v1/evaluations/{id}/activity`. The tab SHALL be partitioned by agent (SME, Coordinator, GAD, ITSO) with the latest event at the bottom of each section. Each event SHALL display its timestamp, category, and a human-readable message derived from the event payload.

#### Scenario: Live event populates the Activity tab
- **WHEN** the workspace is open and the supervisor emits a `[SME_GROUPED]` event for basket A1
- **THEN** the SSE endpoint SHALL push the event to the connected client
- **AND** the SME section of the Activity tab SHALL show the new event with its timestamp
- **AND** the message SHALL describe the basket extraction in human-readable form

#### Scenario: Late-joining client receives a buffer replay
- **WHEN** a faculty member opens the workspace 30 seconds into a running evaluation
- **THEN** the SSE endpoint SHALL first replay the most recent N events from the per-job buffer
- **AND** SHALL then continue streaming live events as they arrive

#### Scenario: SSE connection drops and reconnects
- **WHEN** the client loses its SSE connection
- **THEN** the client SHALL automatically reconnect after a backoff
- **AND** the reconnection SHALL replay the buffer up to the most recent event the client has already shown
- **AND** SHALL continue streaming live events after the replay

#### Scenario: Event categories match the existing log categories
- **WHEN** the supervisor, SME, Coordinator, GAD, or ITSO emits a log line in one of the existing categories (`[EVAL_TIMING]`, `[SME_GROUPED]`, `[ENGINE_TIMING]`, `[EVAL_PROMPT_BUDGET]`, `[EVAL_PROMPT_SIZE]`)
- **THEN** the same call site SHALL also push a typed event into the per-job buffer
- **AND** the stdout log line SHALL continue to be emitted unchanged
- **AND** the SSE endpoint SHALL stream the typed event to the client

### Requirement: Artifacts tab shows persisted chunks, rubric, and policy
The `Artifacts` tab SHALL display the artifacts relevant to the active evaluation: the persisted SLM chunks (ordered by page and chunk index), the rubric excerpts used by the SME and Coordinator, and any policy evidence surfaced to ITSO. Each artifact row SHALL be clickable to expand its full text or to jump to the source location in the document preview.

#### Scenario: Persisted chunks are listed
- **WHEN** the `Artifacts` tab is opened
- **THEN** the workspace SHALL query the persisted SLM chunks for the evaluation's document
- **AND** SHALL list them with page number, chunk index, and a snippet of the chunk text

#### Scenario: Rubric excerpts are listed
- **WHEN** the SME and Coordinator have used rubric excerpts during the run
- **THEN** the `Artifacts` tab SHALL list those excerpts
- **AND** clicking an excerpt SHALL reveal the full rubric context

#### Scenario: Policy evidence is listed
- **WHEN** ITSO has surfaced policy evidence during the run
- **THEN** the `Artifacts` tab SHALL list the cited policy chunks
- **AND** SHALL NOT expose the policy as faculty-selectable — only as read-only evidence

### Requirement: Scorecard tab becomes the default on lifecycle completion
The `Scorecard` tab SHALL display the same scorecard the existing two-pane view displays: domain scores, per-criterion scores, the monitoring matrix flags, the PDF export action, and (when applicable) the curriculum-alignment and syllabus-alignment links. The tab SHALL become the default the first time the lifecycle reaches a terminal state in the current session.

#### Scenario: Scorecard renders the terminal result
- **WHEN** the lifecycle is `COMPLETED` and the Scorecard tab is active
- **THEN** the tab SHALL render the same data the current scorecard view shows: synthesized score, domain breakdown, criterion scores, monitoring matrix flags, PDF export
- **AND** existing curriculum-alignment and syllabus-alignment entry points (if any) SHALL remain reachable from the tab

#### Scenario: Scorecard renders a FAILED result
- **WHEN** the lifecycle is `FAILED` and the user opens the Scorecard tab
- **THEN** the tab SHALL render a failure state with the error message
- **AND** SHALL offer a way to open the full report (read-only, no retry from the tab — the retry button lives in the existing evaluation page or the History list)

#### Scenario: Scorecard renders a COMPLETED_PARTIAL result
- **WHEN** the lifecycle is `COMPLETED_PARTIAL`
- **THEN** the tab SHALL render the partial scorecard
- **AND** SHALL display a partial-acknowledgement chip explaining the no-curriculum cause
- **AND** SHALL mark Coordinator as `skipped_partial` rather than `failed`

### Requirement: Two-layer faculty sidebar
The faculty sidebar SHALL have two layers in the same column. Layer 1 is the logo and the top-level navigation (Library, Documents, Advisory, History, Admin). Layer 2 is a recent-sessions list, ordered newest-first, flat (no grouping), with each item showing `program — course code — title — lifecycle pill`. Layer 2 SHALL read from the existing `useEvaluationHistory` query, limited to the most recent N sessions (default 10) for the current user. Admin mode SHALL skip Layer 2 entirely and keep the existing admin sidebar shape.

#### Scenario: Faculty sees Layer 1 navigation
- **WHEN** a faculty member opens any page in the app
- **THEN** the sidebar SHALL show Layer 1: logo and the top-level nav buttons (Library, Documents, Advisory, History, Admin)
- **AND** SHALL render Layer 2 below Layer 1 with the recent-sessions list

#### Scenario: Recent-sessions list reflects the history query
- **WHEN** Layer 2 renders
- **THEN** the list SHALL show the most recent N evaluations for the authenticated user
- **AND** each item SHALL display `program — course code — title — lifecycle pill`
- **AND** clicking an item SHALL navigate to that evaluation's workspace

#### Scenario: Admin mode bypasses Layer 2
- **WHEN** an authenticated admin opens any page
- **THEN** the sidebar SHALL render the existing admin sidebar (no Layer 2)
- **AND** SHALL not show the recent-sessions list

#### Scenario: Layer 2 has no pin or star control
- **WHEN** Layer 2 renders
- **THEN** no pin, star, or favorite control SHALL be present
- **AND** the list SHALL be ordered strictly newest-first from the history query

### Requirement: Both evaluation routes resolve to the same workspace
The router SHALL map `/documents/$documentId/evaluation` and `/evaluations/$id` to the same `EvaluationWorkspacePage`. The router SHALL derive the evaluation from the document id (when the URL is `/documents/$id/evaluation`) or use the evaluation id directly (when the URL is `/evaluations/$id`). The URL the user clicked SHALL be preserved (no rewrite).

#### Scenario: Click-through from the Documents page
- **WHEN** a faculty member clicks a row in the Documents page
- **THEN** the router SHALL navigate to `/documents/$documentId/evaluation`
- **AND** SHALL resolve the workspace to the document's most recent evaluation
- **AND** SHALL render the workspace for that evaluation

#### Scenario: Direct link from the History list
- **WHEN** a faculty member clicks a row in the History list
- **THEN** the router SHALL navigate to `/evaluations/$id`
- **AND** SHALL render the workspace for that evaluation directly

#### Scenario: URL is preserved on the workspace
- **WHEN** a faculty member is on `/documents/$documentId/evaluation`
- **THEN** the URL SHALL NOT rewrite to `/evaluations/$id`
- **AND** the URL SHALL remain the one the user clicked

### Requirement: Programs in scope are BSInfoTech and BSCS
The workspace SHALL honor the existing program scope: `BSInfoTech` is the canonical code; `BSIT` is a read alias. `BSCS` is a second canonical code. The workspace SHALL display the program as read-only metadata (per the locked scope: auto-program at upload is deferred). BSCS sessions are allowed; the standard evaluation runs; curriculum alignment will report `UNAVAILABLE` for BSCS until a map is seeded (the existing curriculum-alignment surface handles that signal).

#### Scenario: Workspace displays the program as read-only metadata
- **WHEN** a faculty member opens the workspace
- **THEN** the workspace SHALL show the SLM's program
- **AND** the program SHALL NOT be editable from the workspace

#### Scenario: BSCS session runs the standard evaluation
- **WHEN** a faculty member opens the workspace for a BSCS evaluation
- **THEN** the standard evaluation SHALL be allowed to run
- **AND** the curriculum-alignment panel (if surfaced) SHALL report `UNAVAILABLE`
- **AND** the syllabus-alignment surface (untouched) SHALL remain available
