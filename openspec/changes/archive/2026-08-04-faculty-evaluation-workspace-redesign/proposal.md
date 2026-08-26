## Why

The current faculty dashboard shows uploaded SLMs as a flat list with a click-through to a completed-evaluation page. While the evaluation pipeline runs four agents in parallel (SME, Coordinator, GAD, ITSO), the faculty member has no live visibility — they only learn the run is done when the polling endpoint returns `COMPLETED`. The dashboard does not surface the evaluation lifecycle visually, does not stream per-agent progress, and treats the running evaluation as a black box. The two existing top-level routes for advisory features (curriculum alignment, syllabus alignment) are kept but the standard evaluation workspace needs the same AI-product-like treatment that the rest of the industry has adopted: see the work happen, then see the result.

This change moves the faculty evaluation view from a "flat list + completed-evaluation page" model to a centered evaluation workspace where the lifecycle is a visible timeline, the four subagents are clickable cards on the `EVALUATING` stage, and a right contextual details panel opens on demand for the selected agent, the artifacts, or the scorecard. A Server-Sent Events stream powers the live activity feed so the faculty member can watch the agents in real time.

## What Changes

- **New** evaluation workspace page (`EvaluationWorkspacePage`) at `/documents/$documentId/evaluation` and `/evaluations/$id` that hosts the lifecycle timeline + four clickable subagent cards + document preview + a right contextual details panel.
- **New** two-layer faculty sidebar: Layer 1 keeps the existing top-level navigation (Library, Documents, Advisory, History, Admin); Layer 2 shows recent evaluation sessions in a flat list (no pin/star for now; pin function is deferred).
- **New** right contextual details panel (`RightDetailsPanel`) that is collapsed by default, opens on agent-card click (`Activity` tab), artifact click (`Artifacts` tab), or lifecycle completion (`Scorecard` tab, default on `COMPLETED`).
- **New** Server-Sent Events endpoint `GET /api/v1/evaluations/{id}/activity` that streams typed per-agent events for the lifecycle. The existing log categories (`[EVAL_TIMING]`, `[SME_GROUPED]`, `[ENGINE_TIMING]`, `[EVAL_PROMPT_BUDGET]`, `[EVAL_PROMPT_SIZE]`) become both log lines and typed events the client can render.
- **New** components: `LifecycleTimeline`, `AgentCardGrid`, `useEvaluationSSE` hook.
- **Modified** `EvaluationInterface.tsx` to be the new centered workspace container; `EvaluationSetup.tsx` integrates as the pre-flight view; `useEvaluationPageState.ts` adds SSE connection state and active agent selection; `DocumentPane.tsx` and `FlagList.tsx` move into the right panel; `Sidebar.tsx` and `AppShell.tsx` refactor for the two-layer layout; `router.tsx` routes both evaluation URLs to the new workspace.
- **Removed** `EvaluationHeader.tsx` (absorbed into the new top header + timeline) and `ScoreDashboard.tsx` (replaced by the center subagent cards + right details panel).
- **Kept** all existing top-level routes (`/dashboard`, `/upload`, `/library`, `/alignment`, `/syllabus-alignment`, `/evaluations`, `/admin/*`) and all advisory feature pages untouched.
- **Deferred**: stop-evaluation button, auto-program at upload, pin/star function, admin dashboard redesign, BSCS curriculum map data, color/typography polish, animation timing. These are recorded in `design.md` § Deferred.

## Capabilities

### New Capabilities

- `faculty-evaluation-workspace`: the new centered evaluation workspace, lifecycle timeline, four subagent cards, right contextual details panel (Activity / Artifacts / Scorecard tabs), and the SSE activity stream that powers them. Covers `/documents/$id/evaluation` and `/evaluations/$id` for the standard evaluation only. The two advisory features (curriculum alignment, syllabus alignment) are out of scope and keep their existing routes and pages.

### Modified Capabilities

- `evaluations`: the lifecycle status is now surfaced as a visible timeline with `SUBMITTED → PREPROCESSING → EVALUATING → SYNTHESIZING → COMPLETED | FAILED | COMPLETED_PARTIAL`. The `EVALUATING` stage hosts the four subagent cards. A new `GET /api/v1/evaluations/{id}/activity` SSE endpoint streams per-agent events for the run. The lifecycle behavior is unchanged; only the client visualization and the SSE surface are added.

## Impact

- **Client code**: `client/src/features/evaluation/{EvaluationInterface,EvaluationSetup,DocumentPane,FlagList,ScoreDashboard,EvaluationHeader,Scorecard}.tsx`, `client/src/features/evaluation/hooks/useEvaluationPageState.ts`, `client/src/app/layout/{Sidebar,AppShell}.tsx`, `client/src/app/router.tsx`, `client/src/features/evaluation/types.ts`.
- **New client files**: `LifecycleTimeline.tsx`, `AgentCardGrid.tsx`, `RightDetailsPanel.tsx`, `useEvaluationSSE.ts`, `useSidebar.ts`.
- **Backend code**: new `GET /api/v1/evaluations/{id}/activity` SSE endpoint in `server/modules/evaluations/router.py` (or a new sibling). The supervisor (`server/modules/agents/supervisor.py`) and the runtime (`server/modules/core/llm.py` or a new `server/modules/evaluations/activity_bus.py`) emit typed events in addition to the existing log lines. The event categories match the existing log categories: `eval_timing`, `sme_grouped`, `engine_timing`, `eval_prompt_budget`, `eval_prompt_size`. The SSE buffer is per-job and replayed to a late-joining client.
- **Scope guardrails**: the standard evaluation is `BSInfoTech` or `BSCS` only. `BSIT` is a read alias for `BSInfoTech`. BSCS sessions are allowed; the standard evaluation runs; the curriculum alignment panel reports `UNAVAILABLE` until a BSCS map is seeded. The admin dashboard is out of scope.
- **No breaking changes** to existing routes, endpoints, or the evaluation lifecycle. Existing polling-based clients keep working.
