## Context

The faculty evaluation view today is a two-pane page (document preview + scorecard) reached by clicking a row in the flat Documents list. The evaluation lifecycle (`SUBMITTED → PREPROCESSING → EVALUATING → SYNTHESIZING → COMPLETED | FAILED | COMPLETED_PARTIAL`) is only visible as a status pill. The four agents (SME, Coordinator, GAD, ITSO) run in parallel via the supervisor's `ThreadPoolExecutor`, but the client has no live visibility — it learns the run is done only when the polling endpoint returns `COMPLETED`. The existing log categories (`[EVAL_TIMING]`, `[SME_GROUPED]`, `[ENGINE_TIMING]`, `[EVAL_PROMPT_BUDGET]`, `[EVAL_PROMPT_SIZE]`) are stdout-only.

This change moves the faculty evaluation view to an AI-product-like centered workspace: the lifecycle is a visible timeline, the four agents are clickable cards on the `EVALUATING` stage, a right contextual details panel opens on demand, and a Server-Sent Events stream powers the live activity feed. The two advisory features (curriculum alignment, syllabus alignment) stay as separate top-level routes. The admin dashboard is out of scope.

The locked design decisions and program scope are recorded in `proposal.md` § Why, What Changes, and Capabilities.

## Goals / Non-Goals

**Goals:**

- Surface the evaluation lifecycle as a visible timeline with `SUBMITTED → PREPROCESSING → EVALUATING → SYNTHESIZING → COMPLETED | FAILED | COMPLETED_PARTIAL`.
- Show the four subagent nodes (SME, Coordinator, GAD, ITSO) as clickable cards on the `EVALUATING` stage, each showing name, model, status, and elapsed time.
- Stream per-agent activity events from the supervisor to the client via Server-Sent Events so the faculty member can watch the agents in real time.
- Open a right contextual details panel on demand: `Activity` tab (the SSE stream, focused on the selected agent), `Artifacts` tab (persisted chunks, rubric, policy), `Scorecard` tab (terminal scorecard + PDF export; default on `COMPLETED`).
- Restructure the faculty sidebar into two layers: Layer 1 keeps the existing top-level navigation; Layer 2 shows recent evaluation sessions in a flat list.
- Keep every existing top-level route, keep the advisory features as separate top-level routes, keep the standalone Documents page, and keep the admin dashboard untouched.
- Honor the locked program scope: `BSInfoTech` (with `BSIT` as a read alias) and `BSCS`. BSCS sessions are allowed; curriculum alignment will report `UNAVAILABLE` until a BSCS map is seeded.

**Non-Goals:**

- A stop-evaluation button. The current `BackgroundTasks` cancel path stays absent. Deferred.
- Auto-program at upload. The upload form keeps an explicit program selector. Deferred.
- A pin/star function for sessions in Layer 2 of the sidebar. Layer 2 is recent-sessions-only. Deferred.
- Admin dashboard redesign. Admin keeps its existing workspace.
- BSCS curriculum map data. Out of scope; the system must allow BSCS sessions but curriculum alignment reports `UNAVAILABLE`.
- Color, typography, animation, and motion polish. The redesign respects the existing LSPU palette (`#1b3b87`, `#f2c811`, `#3b963e`, `#b91c1c`), Inter typography, and flat-elevation rules; visual polish happens in a follow-up.
- A refactor of the evaluation pipeline itself. The lifecycle, persistence, and agent contracts are unchanged.
- Any new backend dependency or third-party service.

## Decisions

### 1. Server-Sent Events for the live activity stream

- **Decision**: SSE, not WebSocket.
- **Rationale**: The activity stream is one-way (server → client). SSE works through the existing FastAPI `BackgroundTasks` without introducing a new connection layer, reuses HTTP/1.1 infrastructure (proxies, auth, CORS), and is much simpler to operate. The drop button (deferred) is the only thing SSE cannot do natively; when that ships, we can either add WebSocket for cancel or implement cancel via a separate POST.
- **Alternatives considered**: WebSocket (rejected: bidirectional capability not needed today, adds a connection layer and a new event protocol). Long polling (rejected: higher latency, more requests, same server load).

### 2. Per-job event buffer for late-joining clients

- **Decision**: Each running job keeps a bounded per-job event buffer in memory. The SSE endpoint subscribes to it; a late-joining client first receives the replay, then live events.
- **Rationale**: The current polling model already survives a client disconnect (the run finishes in the background, the next poll returns the terminal state). SSE must match that. Without a buffer, a client that connects 30s into a run sees nothing until the next event. With a buffer of the last N events, the client gets the meaningful history.
- **Bound**: 500 events per job (~50KB at 100 bytes/event). On overflow, drop oldest. The lifecycle completion is always retained as a sentinel event.
- **Alternatives considered**: Persist events to the DB. Rejected: doubles the write load for a feature that is advisory visualization, not audit.

### 3. Event categories match the existing log categories

- **Decision**: The SSE event types mirror the existing log categories: `eval_timing`, `sme_grouped`, `engine_timing`, `eval_prompt_budget`, `eval_prompt_size`, plus a new `lifecycle` category for stage transitions.
- **Rationale**: The supervisor, SME, Coordinator, GAD, and ITSO already emit these log lines. Promoting them to typed events is additive — the log lines still go to stdout. Each log call site emits both a log line and an event into the job's buffer.
- **Schema** (per event): `{job_id, ts, agent, category, stage, message, payload?}`. `payload` is category-specific (e.g., `eval_timing` includes `seconds`; `sme_grouped` includes `basket` and `outcome`).

### 4. Right contextual details panel as a context-driven tab system

- **Decision**: The right panel is collapsed by default. Tabs open in response to clicks: agent card → `Activity` tab, artifact row → `Artifacts` tab, lifecycle completion → `Scorecard` tab (default).
- **Rationale**: A persistent fixed-menu right panel forces the faculty member to manage a sidebar that doesn't apply to the current view. Context-driven tabs match Linear, Notion, and Vercel. The Scorecard tab is the default on `COMPLETED` because that's the natural end state.
- **Alternatives considered**: Fixed three-tab right panel (rejected: always-on sidebar noise). Single drawer that swaps content (rejected: loses the sense of "I'm in the scorecard view" the tabs provide).

### 5. Two-layer sidebar with flat recent-sessions list

- **Decision**: Layer 1 (logo + nav buttons) is always visible. Layer 2 (recent sessions) is always visible in the same column, below the nav. The list is flat (no grouping by course/program) and ordered newest-first.
- **Rationale**: Keeping the navigation simple avoids the pin/star complexity for now. A flat list with `program — course code — title — lifecycle pill` is enough to scan. Grouping adds clicks; the user explicitly asked to "keep it simple for now."
- **Recent-sessions data source**: extend `useEvaluationHistory` to return the most recent N evaluations (default 10) for the current user, regardless of program. No new backend endpoint required — the existing history query is sufficient.
- **Alternatives considered**: Grouped by course (rejected: extra clicks). Pinned + recent (rejected: pin function is deferred). Collapsible Layer 2 (rejected: complicates layout math; the existing sidebar already collapses to icons).

### 6. Lifecycle timeline maps to the existing status field

- **Decision**: The `LifecycleTimeline` component reads `EvaluationStatusResponse.status` and renders the corresponding stage as active or completed. No new backend state.
- **Rationale**: The lifecycle is already persisted and exposed via `GET /evaluations/{id}/status`. The timeline is a client-only visualization layer.
- **`EVALUATING` substate**: the four subagent cards appear on this stage. Each card reads its own status from the SSE stream. A subagent that hasn't been seen yet is `pending`; one that has emitted a `sme_grouped` (or equivalent) event is `running`; one that has emitted a terminal event (e.g., `engine_timing` with `outcome=ok`) is `done`. A subagent that has emitted an `error` event is `failed`.

### 7. Routing — both evaluation URLs go to the new workspace

- **Decision**: `/documents/$documentId/evaluation` and `/evaluations/$id` both resolve to `EvaluationWorkspacePage`. The router derives the job from the document or evaluation id and looks up the evaluation internally.
- **Rationale**: Today both URLs lead to the same two-pane view; consolidating them into one workspace preserves the existing entry points (Documents click-through and direct History link) and makes the workspace the single destination.
- **No new redirect**: the existing routes are repurposed in place; deep links from the old dashboard keep working.

### 8. Programs in scope are BSInfoTech and BSCS

- **Decision**: The new workspace honors the existing program scope. `BSInfoTech` is the canonical code; `BSIT` is a read alias. `BSCS` is the second canonical code.
- **Rationale**: The locked scope from `proposal.md`. BSCS sessions are allowed; the standard evaluation runs; the curriculum alignment panel reports `UNAVAILABLE` until a BSCS map is seeded (the syllabus-alignment surface is untouched, so the user can still run syllabus alignment on BSCS SLMs once a syllabus is uploaded).
- **No auto-program**: the upload form keeps its explicit program selector (per the deferred-item list).

## Risks / Trade-offs

- **[SSE through FastAPI sync endpoints]** → the SSE response is a streaming response; FastAPI handles it natively via `StreamingResponse`. The supervisor and agent code stay synchronous; events are pushed into a thread-safe buffer. Verified that the existing `BackgroundTasks` does not block SSE responses.
- **[Per-job buffer memory]** → 500 events × 100 bytes = ~50KB per concurrent job. With the limiter cap of 4 concurrent evaluations plus 1 advisory run, the worst case is ~250KB across all jobs. Acceptable.
- **[Event log duplication]** → each log call site now emits both a stdout line and an event. The supervisor's hot path runs at most ~10 log calls per evaluation; the duplication cost is negligible.
- **[Lifecycle timeline for `COMPLETED_PARTIAL` and `FAILED`]** → both states render as terminal pills with the appropriate color and a tooltip explaining the cause. The right panel defaults to `Scorecard` (for `COMPLETED_PARTIAL`) or `Activity` (for `FAILED`, so the user sees what failed).
- **[Long-running evaluations with the right panel closed]** → the timeline and the agent cards always show live state. Closing the right panel does not stop the SSE subscription; the client just stops rendering the activity stream until a tab is opened.
- **[Client disconnect during a run]** → the SSE endpoint removes the subscriber from the buffer's subscriber list. The run continues server-side; a reconnecting client receives the buffer replay.
- **[Tab scroll behavior]** → when the user clicks an agent card, the `Activity` tab opens scrolled to that agent's section. The scroll position is recomputed on every event, not on every render.
- **[Existing polling clients]** → the new `GET /evaluations/{id}/status` and `GET /evaluations/{id}` endpoints are unchanged. Existing clients that poll keep working; the SSE endpoint is additive.
- **[Document preview in the new workspace]** → the document preview is embedded in the workspace center as a collapsible panel below the agent cards, not in the right details panel. The Artifacts tab shows extracted chunks (for evidence-link purposes), not the full PDF.
- **[Mobile / narrow viewports]** → the new workspace is desktop-first. Below 1024px, the right panel becomes a full-screen modal on agent-card click, and the document preview collapses to a drawer. The two-layer sidebar collapses to icons (existing behavior). Mobile polish is a follow-up; the locked scope is desktop.

## Migration Plan

1. **Ship the new workspace behind the same URLs** (`/documents/$id/evaluation` and `/evaluations/$id`). The old `EvaluationInterface` is replaced in place; the old `ScoreDashboard` and `EvaluationHeader` are removed. No URL changes; no redirects needed.
2. **Add the SSE endpoint** (`GET /api/v1/evaluations/{id}/activity`) as a new route. The supervisor's existing log call sites are augmented to also push into the per-job event buffer; stdout logging is unchanged.
3. **Roll the sidebar change** in one commit: Layer 1 unchanged, Layer 2 added below it. The nav buttons are unchanged; the recent-sessions list is read from the existing history query.
4. **Cut a small vertical slice first** (Phase 1 of the task list): the lifecycle timeline + the four subagent cards + the SSE activity stream. Defer the right panel to Phase 2 and the sidebar Layer 2 to Phase 3. This keeps each commit reviewable.
5. **Rollback**: revert the affected files. The SSE endpoint is additive (no existing client depends on it). The new workspace replaces the old `EvaluationInterface` in place; rolling back restores the old two-pane view. No data migration needed.
6. **No database migration**. The new `provenance` JSON column on `curriculum_alignment_checks` (from the earlier curriculum-alignment work) is reused for SSE event history if needed; the existing lifecycle status is the only authoritative state.

## Open Questions

- **[Q1] SSE heartbeat**: SSE connections can be closed by intermediate proxies after long idle periods. Should the server emit a `: keepalive` comment every 15s? (My recommendation: yes; trivial cost.)
- **[Q2] Event retention after job completion**: how long does the per-job buffer live after the lifecycle hits a terminal state? (My recommendation: 1 hour, then evict; the history query is the durable record.)
- **[Q3] `COMPLETED_PARTIAL` right-panel default**: should it default to `Scorecard` (the user can see why it's partial) or `Activity` (the user can see what happened)? (My recommendation: `Scorecard` with the partial-acknowledgement chip prominent; the cause is in the scorecard metadata.)
- **[Q4] `EVALUATING` stage timeout visualization**: the supervisor already has a heartbeat; the timeline should show "stuck at EVALUATING for Xs" if no events have arrived in 30s. (My recommendation: yes, a subtle pulse on the stage label; no separate alert.)
- **[Q5] Two-evaluation routing**: both URLs resolve to the same workspace. Should the URL update when the user lands on `/documents/$id/evaluation` (i.e., rewrite to `/evaluations/$id`)? (My recommendation: keep the URL the user clicked; document derivation happens client-side.)
- **[Q6] Layer 2 ordering on revisit**: when a faculty member returns to the workspace, does Layer 2 jump to the current evaluation? (My recommendation: Layer 2 always shows the most recent N; the current evaluation is whichever the URL points to. No auto-jump.)
- **[Q7] BSCS `UNAVAILABLE` for curriculum alignment**: surfaced where? (My recommendation: a new "Curriculum alignment" panel in the `Scorecard` tab, hidden for `BSInfoTech` and present-but-`UNAVAILABLE` for `BSCS` until a map is seeded. Out of scope for this change; the curriculum-alignment panel lives in the existing curriculum-alignment work. The new workspace simply does not surface it.)
