## Why

In operational validation with domain experts at Laguna State Polytechnic University – Santa Cruz Campus (LSPU SCC), reviewers are assigned to specific evaluation roles (SME, Program Coordinator, GAD, or ITSO). The current system forces every evaluation into an all-or-nothing 4-agent bundle requiring 2–3 minutes of compute, mandatory curriculum dependencies, and complex "partial without curriculum" workarounds.

This change transforms evaluation into a targeted single-agent workflow where domain experts execute only their assigned specialist role on demand (~20–30s runtime), eliminating cross-agent blocking and establishing a progressive 4-domain accreditation checklist.

## What Changes

- **Targeted Single-Agent Submission**: `POST /api/v1/evaluations/` accepts `target_agent: Literal["sme", "coordinator", "gad", "itso"]`. Each evaluation job schedules and executes strictly one agent.
- **Domain-Specific Reference Gating**: Reference document dependencies are decoupled:
  - `sme`, `gad`, and `itso` evaluate the SLM immediately with zero curriculum dependency.
  - Only `coordinator` requires an authoritative curriculum context.
- **Progressive 4-Domain Checklist Matrix**:
  - `monitoring_matrix` retains one row per document (`UNIQUE(document_id)`).
  - Evaluated domains update `domain_scores_json[target_agent]` independently.
  - Status reflects progressive completion: `IN_PROGRESS` while 1–3 domains are evaluated; `COMPLETED` once all 4 domains are finished.
  - `synthesized_score` is finalized once all 4 domains are completed.
- **Deprecation of "Partial without Curriculum" Mode**:
  - Because agents run independently, an evaluation is never "partial." If GAD runs, it is a 100% complete GAD evaluation.
  - `partial_without_curriculum` and `partial_reason` are deprecated.
- **Simplified Frontend Review Workflow**:
  - Replaces the 939-line `EvaluationSetup.tsx` wizard monolith with a concise, role-targeted trigger modal.
  - Document table and ledger rows display role action buttons (`Evaluate as GAD`, `Evaluate as SME`, etc.) and progressive completion indicators.

## Capabilities

### New Capabilities
<!-- No brand new capability paths; this restructures the core evaluation workflow -->

### Modified Capabilities
- `evaluations`: Restructures job submission from a 4-agent bundle to a single targeted agent. Deprecates `partial_without_curriculum` mode and isolates curriculum requirements strictly to the Coordinator role.
- `monitoring-matrix`: Restructures matrix state from a single-run composite to a progressive checklist accumulating domain evaluations over time until full 4-domain completion.

## Impact

- **Database**:
  - `evaluation_jobs`: Add non-null `target_agent VARCHAR(32)` column via Alembic migration; backfill historical rows with `'all'`.
  - `monitoring_matrix`: Progressive deep-merging of `domain_scores_json` and rolling domain counts.
- **Backend APIs**:
  - `POST /api/v1/evaluations/`: **BREAKING** `target_agent` is required in the submit payload. `confirmed_program` remains required. `curriculum_id` is required only when `target_agent == "coordinator"`.
- **Performance**:
  - Evaluation runtime drops from 120–180 seconds down to 20–30 seconds per evaluation job.
  - Eliminates thread pool lock contention and multi-agent heartbeat races.
- **Frontend UX**:
  - Deletes complex mode/acknowledge checkboxes.
  - Replaces `EvaluationSetup.tsx` with a lightweight confirmation modal.
