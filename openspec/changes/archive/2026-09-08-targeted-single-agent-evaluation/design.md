## Context

See `proposal.md` for motivation. Currently, `EvaluationJob` forces a parallel 4-agent execution bundle (`sme`, `coordinator`, `gad`, `itso`). This requires complex partial-mode handling when curriculum references are missing, consumes 2–3 minutes of compute per submission, and conflicts with the real-world review model where university domain experts evaluate documents strictly within their assigned roles.

## Goals / Non-Goals

**Goals:**
- Enable targeted single-agent execution: each evaluation job runs exactly one agent specified by `target_agent: Literal["sme", "coordinator", "gad", "itso"]`.
- Decouple reference dependencies: `sme`, `gad`, and `itso` execute immediately on the SLM text with zero curriculum dependency. Only `coordinator` requires curriculum context.
- Implement a progressive 4-domain checklist in `monitoring_matrix`: individual domain evaluations update `domain_scores_json[target_agent]` independently over time, transitioning to `COMPLETED` and finalizing `synthesized_score` once all 4 domains complete.
- Reduce evaluation latency from ~120–180s to ~20–30s per job.
- Replace the 939-line `EvaluationSetup.tsx` wizard monolith with a concise, role-targeted trigger modal.

**Non-Goals:**
- Merging the 4 specialist agents into a single generic evaluator prompt (specialist personas, prompt budgets, and individual rubric forms are strictly preserved).
- Removing the institutional composite score (`AGENT_WEIGHTS`) — the composite score is retained and computed once all 4 domains are finished.
- Modifying the underlying agent prompt builders or deterministic scoring calculators.

## Decisions

### Decision 1: `target_agent` on `evaluation_jobs` & Alembic Migration
- **Rationale**: `EvaluationJob` needs an explicit column identifying which specialist agent it represents.
- **Contract**: `target_agent VARCHAR(32) NOT NULL` with values in `("sme", "coordinator", "gad", "itso")`.
- **Migration**: Add column as nullable, backfill historical rows with `'all'` (preserving legacy 4-agent bundle history), then alter to non-null with a composite index on `(document_id, target_agent)`.

### Decision 2: Progressive `MonitoringMatrix` State Machine
- **Rationale**: Maintain a single source of truth per document (`UNIQUE(document_id)`) while allowing domain experts to evaluate independently at different times.
- **Mechanics**:
  - `domain_scores_json`: Deep-merges newly evaluated domain results (e.g. `{"sme": {...}}` $\to$ `{"sme": {...}, "gad": {...}}`).
  - `flag_count`: Sums active flags across evaluated domains.
  - `evaluation_status`:
    - `SUBMITTED`: Job queued; 0 domains evaluated.
    - `IN_PROGRESS`: 1 to 3 domains evaluated. `synthesized_score` remains `null`.
    - `COMPLETED`: All 4 domains (`sme`, `coordinator`, `gad`, `itso`) evaluated. `synthesized_score` is computed via `AGENT_WEIGHTS`.
    - `FAILED`: An active single-agent run suffered an unrecoverable failure.

### Decision 3: Decoupled Reference Gating & Coordinator Isolation
- **Rationale**: Currently, `check_curriculum_readiness` gates the entire evaluation pipeline. This is only relevant for the Program Coordinator.
- **Contract**:
  - `sme`, `gad`, `itso`: Require `document_id` and `confirmed_program`. Zero curriculum checks.
  - `coordinator`: Requires `document_id`, `confirmed_program`, and either a pre-linked curriculum on the document or `curriculum_id` in the request payload.

### Decision 4: Deprecating `partial_without_curriculum` Mode
- **Rationale**: In the single-agent model, an evaluation is never "partial." An evaluation is 100% complete for its target domain.
- **Contract**: `partial_without_curriculum` and `partial_reason` columns on `evaluation_jobs` are deprecated and defaulted to `False`/`None`.

### Decision 5: Frontend Simplification & Role Action Menus
- **Rationale**: The 939-line `EvaluationSetup.tsx` wizard was built for mode selection (full vs partial) and curriculum picking.
- **Contract**:
  - In `DocumentTable.tsx` and `RecentSlmsLedger.tsx`: Add a role-action dropdown menu (`Evaluate as SME`, `Evaluate as GAD`, `Evaluate as ITSO`, `Evaluate as Coordinator`).
  - Clicking an action opens `<EvaluationConfirmModal/>` (~80 lines). If Coordinator is clicked and no curriculum is linked, the modal prompts the user to select a verified curriculum reference.

## Risks / Trade-offs

- **Intermediate Matrix Visibility**:
  - *Risk*: A document with 2 completed domains is `IN_PROGRESS`. Admins might mistake this for an active running job.
  - *Mitigation*: The UI matrix renders domain badges explicitly (e.g. `SME: 3.50`, `GAD: 4.00`, `ITSO: Pending`, `Coord: Pending`) and displays progress chips (`2/4 Domains`).
- **Historical Data Compatibility**:
  - *Risk*: Historical evaluations in the database ran all 4 agents in one job.
  - *Mitigation*: Backfilling historical jobs with `target_agent = 'all'` preserves historical scorecard rendering without branching database queries.
- **Coordinator Curriculum Prerequisite**:
  - *Risk*: If a reviewer triggers Coordinator without curriculum, it must fail fast before model inference.
  - *Mitigation*: The service validates curriculum presence during submission and rejects with HTTP 422 before queue admission.
