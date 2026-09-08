## 1. Database Schema & Migration

- [x] 1.1 Create Alembic migration adding `target_agent VARCHAR(32)` to `evaluation_jobs` with backfill `'all'` for historical rows and composite index on `(document_id, target_agent)`
- [x] 1.2 Update SQLAlchemy model `EvaluationJob` in `server/modules/evaluations/models.py` to declare `target_agent: Mapped[str]` and deprecate `partial_without_curriculum` / `partial_reason`

## 2. Backend Submission API & Service Gating

- [x] 2.1 Update `server/modules/evaluations/schemas.py`: add `target_agent: Literal["sme", "coordinator", "gad", "itso"]` to `EvaluationSubmitRequest`, `EvaluationResponse`, and `EvaluationListItem`
- [x] 2.2 Update `server/modules/evaluations/service.py:create_evaluation`: accept and persist `target_agent`, decouple curriculum requirement so only `target_agent == "coordinator"` requires curriculum context
- [x] 2.3 Update `server/modules/evaluations/agent_schedule.py`: simplify `scheduled_agent_ids(target_agent)` to return `(target_agent,)`

## 3. Orchestrator & Progressive Matrix Synthesis

- [x] 3.1 Update `server/modules/evaluations/orchestrator.py`: resolve form snapshot strictly for `(job.target_agent,)` and dispatch single targeted agent
- [x] 3.2 Update `server/modules/synthesis/matrix.py:upsert_monitoring_matrix`: implement progressive deep-merging of `domain_scores_json[target_agent]`, setting `IN_PROGRESS` (1–3 domains) or `COMPLETED` (4 domains) with final composite score
- [x] 3.3 Add/update backend tests in `server/tests/evaluations/` and `server/tests/synthesis/` verifying single-agent execution and progressive matrix updates

## 4. Frontend API & Document Action Triggers

- [x] 4.1 Update `client/src/features/evaluation/api/evaluation.api.ts` and `types.ts` to include `target_agent` in submit requests
- [x] 4.2 Replace `EvaluationSetup.tsx` with a lightweight `<EvaluationConfirmModal/>` (~80 lines) triggering single-agent evaluation
- [x] 4.3 Update `DocumentTable.tsx` and `RecentSlmsLedger.tsx` to display role-based action triggers (`Evaluate as SME`, `Evaluate as GAD`, `Evaluate as ITSO`, `Evaluate as Coordinator`)
- [x] 4.4 Update `MonitoringTable.tsx` and `ScoreDashboard.tsx` to display progressive domain completion badges and checklist statuses

## 5. End-to-End Verification

- [x] 5.1 Run backend test suite `uv run --project server pytest server/tests/evaluations/ server/tests/synthesis/ -q`
- [x] 5.2 Run frontend test suite `pnpm --dir client test src/features/evaluation/ src/features/documents/`
- [x] 5.3 Execute end-to-end smoke test validating single-agent evaluation and progressive matrix transitions
