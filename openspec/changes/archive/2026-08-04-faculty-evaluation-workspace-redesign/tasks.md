## 1. Backend SSE foundation

- [x] 1.1 Add `ActivityBus` module in `server/modules/evaluations/activity_bus.py`: a thread-safe per-job event buffer with `publish(job_id, event)`, `subscribe(job_id)`, `unsubscribe(job_id, subscriber)`, and a bounded replay of the most recent 500 events. Retain a terminal lifecycle event sentinel.
- [x] 1.2 Add a typed `ActivityEvent` schema (Pydantic) with `job_id, ts, agent, category, stage, message, payload` in `server/modules/evaluations/activity_schemas.py`. Categories: `lifecycle`, `eval_timing`, `sme_grouped`, `engine_timing`, `eval_prompt_budget`, `eval_prompt_size`, `error`.
- [x] 1.3 Augment the supervisor in `server/modules/agents/supervisor.py`: every existing log call site that emits one of the five log categories also publishes an `ActivityEvent` to the `ActivityBus`. The existing stdout log line stays unchanged.
- [x] 1.4 Augment the four agents in `server/modules/agents/{sme,coordinator,gad,itso}.py` (and the engine-scoring modules they call): every existing log call site in the same five categories publishes an `ActivityEvent`. Stdout logging unchanged.
- [x] 1.5 Emit a `lifecycle` event on every status transition in `server/modules/evaluations/service.py::transition_evaluation_status` so the SSE stream can drive the timeline visualization.
- [x] 1.6 Add `GET /api/v1/evaluations/{id}/activity` in `server/modules/evaluations/router.py` returning a `StreamingResponse` with `media_type="text/event-stream"`. Require `require_authenticated_user` and `_require_owned_job`. On connect: replay buffer, then subscribe. Emit `: keepalive` every 15s. On disconnect: unsubscribe.
- [x] 1.7 Add a one-hour eviction sweep for terminal jobs: `ActivityBus.evict_terminal_older_than(older_than_seconds=3600)`. Call from a FastAPI startup hook in `server/main.py` and on a periodic background task.
- [x] 1.8 Add focused unit tests for `ActivityBus` (thread safety, bounded buffer, terminal sentinel, eviction) in `server/tests/evaluations/test_activity_bus.py`.

## 2. Workspace page skeleton and routing

- [x] 2.1 Add `client/src/features/evaluation/pages/EvaluationWorkspacePage.tsx` as the new centered workspace container. Hosts the top header, the `LifecycleTimeline`, the `AgentCardGrid`, the document preview, and the right `RightDetailsPanel`.
- [x] 2.2 Update `client/src/app/router.tsx`: route `/documents/$documentId/evaluation` and `/evaluations/$id` to `EvaluationWorkspacePage`. The page derives the evaluation from the document id (latest) or uses the evaluation id directly. Preserve the URL the user clicked.
- [x] 2.3 Update `client/src/features/evaluation/hooks/useEvaluationPageState.ts` to add SSE connection state (`sseStatus: connecting | open | closed | error`), active agent card selection, and right-panel tab state. Keep the existing polling, document resolution, and result fetching intact.
- [x] 2.4 Move `client/src/features/evaluation/components/EvaluationInterface.tsx`, `EvaluationHeader.tsx`, and `ScoreDashboard.tsx` into the new workspace. `EvaluationHeader` and `ScoreDashboard` are removed; their responsibilities are absorbed by the new top header, the timeline, the agent cards, and the right `Scorecard` tab.
- [x] 2.5 Update `client/src/features/evaluation/components/EvaluationSetup.tsx` to integrate as the workspace pre-flight view (the program selector, partial acknowledgement, and the start button) before the run begins.

## 3. Lifecycle timeline and subagent cards

- [x] 3.1 Add `client/src/features/evaluation/components/LifecycleTimeline.tsx`: a horizontal step indicator rendering the five stages with pending/active/complete/terminal states. Reads `EvaluationStatusResponse.status` from `useEvaluationPageState`. Tooltip on `FAILED` and `COMPLETED_PARTIAL` explains the cause.
- [x] 3.2 Add `client/src/features/evaluation/components/AgentCardGrid.tsx`: four cards (SME, Coordinator, GAD, ITSO). Each card shows name, model, status, elapsed time, and is clickable when at least one event for that agent has been received. Clicking opens the right `Activity` tab focused on that agent.
- [x] 3.3 Add agent-status derivation in `client/src/features/evaluation/utils/agentStatus.ts` (or similar): derive `pending | running | done | failed` from the SSE event stream for each agent. Stale detection: if no event for an agent in 30s while lifecycle is `EVALUATING`, the card shows a subtle "stuck" pulse on the elapsed time.
- [x] 3.4 Wire the lifecycle timeline and the agent card grid into the new `EvaluationWorkspacePage`. The `EVALUATING` stage hosts the four cards; the timeline sits above the cards.
- [x] 3.5 Add focused unit tests in `client/src/features/evaluation/components/__tests__/LifecycleTimeline.test.tsx` and `AgentCardGrid.test.tsx` covering pending/active/complete/terminal states, click-to-open, and stuck-pulse behavior.

## 4. SSE client hook and Activity tab

- [x] 4.1 Add `client/src/features/evaluation/hooks/useEvaluationSSE.ts`: an `EventSource` subscription to `/api/v1/evaluations/{id}/activity`. Reconnects on disconnect with exponential backoff. Exposes `events: ActivityEvent[]`, `status: connecting | open | closed | error`, and an `agentFilter: agent | null` to focus on one agent.
- [x] 4.2 Add `ActivityEvent` and related types in `client/src/features/evaluation/types.ts` matching the backend schema.
- [x] 4.3 Add `client/src/features/evaluation/components/RightDetailsPanel.tsx`: collapsed-by-default drawer with three tabs (`Activity`, `Artifacts`, `Scorecard`). Tabs are context-driven (not a fixed menu): agent card click → `Activity`; artifact click → `Artifacts`; lifecycle terminal → `Scorecard` default. Each tab preserves its scroll position when switching.
- [x] 4.4 Add `client/src/features/evaluation/components/ActivityTab.tsx`: the SSE stream view, partitioned by agent with the latest event at the bottom of each section. Human-readable messages derived from the event payload. Scroll target API for `agentFilter`.
- [x] 4.5 Wire the `Activity` tab to `useEvaluationSSE` and `useEvaluationPageState`. Clicking an agent card sets `agentFilter` and opens the right panel with `Activity` active.
- [x] 4.6 Add focused unit tests in `client/src/features/evaluation/hooks/__tests__/useEvaluationSSE.test.ts` and `components/__tests__/ActivityTab.test.tsx` covering reconnection, agent filter, and the human-readable message derivation.

## 5. Artifacts tab

- [x] 5.1 Add `client/src/features/evaluation/components/ArtifactsTab.tsx`: lists persisted SLM chunks (page + chunk index + snippet), rubric excerpts used by SME/Coordinator, and ITSO policy evidence. Each row expands to show the full text and is clickable to jump to the source location in the document preview.
- [x] 5.2 Move `client/src/features/evaluation/components/DocumentPane.tsx` and `FlagList.tsx` into the `Artifacts` tab or the document preview embedded in the workspace. `FlagList` becomes an `Activity` tab section showing monitoring matrix flags.
- [x] 5.3 Add focused tests in `components/__tests__/ArtifactsTab.test.tsx` covering chunk listing, rubric excerpts, policy evidence, and click-to-jump.

## 6. Scorecard tab

- [x] 6.1 Add `client/src/features/evaluation/components/ScorecardTab.tsx`: renders the same data as the existing `Scorecard.tsx` (synthesized score, domain breakdown, criterion scores, monitoring matrix flags, PDF export) plus the partial-acknowledgement chip on `COMPLETED_PARTIAL` and a failure state on `FAILED` that links to the full report.
- [x] 6.2 Make `ScorecardTab` the default the first time the lifecycle reaches a terminal state in the current session. Persist a `scorecardDefaulted: true` flag in the `useEvaluationPageState` reducer so the default fires exactly once per session.
- [x] 6.3 Reuse the existing `Scorecard.tsx` and `ScorecardPdfExport.tsx` inside `ScorecardTab` rather than duplicating their logic.
- [x] 6.4 Add tests in `components/__tests__/ScorecardTab.test.tsx` covering `COMPLETED`, `FAILED`, `COMPLETED_PARTIAL`, the once-per-session default, and PDF export.

## 7. Two-layer faculty sidebar

- [x] 7.1 Refactor `client/src/app/layout/Sidebar.tsx` to render two layers in the same column. Layer 1: logo + top-level nav (Library, Documents, Advisory, History, Admin). Layer 2: recent-sessions list (flat, newest-first, no pin/star). Admin mode skips Layer 2 entirely.
- [x] 7.2 Add `client/src/shared/hooks/useSidebar.ts` for Layer 2 collapse state and active session selection. Admin mode bypasses the hook.
- [x] 7.3 Update `client/src/app/layout/AppShell.tsx` to adjust header offset and any layout math for the two-layer sidebar.
- [x] 7.4 Add `client/src/features/evaluation/utils/recentSessions.ts` (or extend `useEvaluationHistory`) to return the most recent N (default 10) evaluations for the current user, regardless of program. No new backend endpoint required.
- [x] 7.5 Add tests in `client/src/app/layout/__tests__/Sidebar.test.tsx` covering Layer 1, Layer 2 (faculty), admin bypass, and the new layout math.

## 8. Program scope, types, and routing verification

- [x] 8.1 Add `client/src/features/evaluation/types.ts` updates: `LifecycleStage`, `AgentName`, `AgentCardStatus`, `ActivityEvent`, `ActivityTabSection`, `RightPanelTab`, `PinnedSession` (stub — unused until the pin function is later unblocked).
- [x] 8.2 Verify the program scope: the workspace displays the SLM's program as read-only metadata (`BSInfoTech`, `BSCS`, with `BSIT` as a read alias). No auto-program change.
- [x] 8.3 Run `pnpm exec tsc --noEmit`, `pnpm test`, and `pnpm lint`. No new lint warnings.
- [x] 8.4 Run `uv run pytest tests/evaluations/ tests/curriculum_map/ -q` and `uv run ruff check server/modules/evaluations/ server/modules/agents/`. No new test failures or ruff errors.
- [x] 8.5 Run `uv run alembic heads` to confirm the schema is unchanged (no new migration in this change).

## 9. Council review and OpenSpec archive

- [x] 9.1 Dispatch the council review (safety / performance / security) for the implemented change.
- [x] 9.2 Address any SHIP-blocking findings from the council.
- [ ] 9.3 Sync the two delta specs (`faculty-evaluation-workspace` and `evaluations`) to `openspec/specs/`.
- [ ] 9.4 Run `openspec validate` for the change and the updated main specs. Address any validation errors.
- [ ] 9.5 Archive the change via `openspec archive` once all artifacts are validated and council approves.
