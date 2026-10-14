# Evaluation harness extraction: migration handoff

**Status:** accepted architecture; execution unstarted  
**Source checkpoint:** `28fbde69cfa82ffda4c35d719495f38f34dba15f` (HEAD; inspected 2026-10-13)  
**Scope protection:** unrelated pre-existing changes are outside scope and must not be staged, committed, overwritten, or included in this migration. Do not conflate Git staging with Workguard promotion. This plan does not imply runtime readiness or completed extraction.

## Outcome and boundaries

Extract the in-process specialist evaluation logic into `libs/evaluation-harness/src/equiped_harness`, in this repository and installed into the existing backend process. This is a Python package, not a service, worker, queue, or new execution tier. The backend calls the library; the library never imports the backend. Backend `modules/agents` becomes a genuine context-preparation, transport, and integration owner, not a duplicate pipeline or permanent forwarding facade.

The harness owns the SME, Coordinator, GAD, and ITSO specialist evaluation pipelines; pure rubric contracts, manifests and calculators; grounding, measurements, bounded repair and scoring; result/provenance contracts; and supported historical evaluator versions. It exposes a narrow typed entry point per specialist. Keep specialist-specific internals in their domain modules; do not impose identical `pipeline.py` files or a plugin framework merely for symmetry.

The package must not import `server.*`, FastAPI, ORM/database APIs, Chroma/retrieval, environment loaders, or default model resolution. It declares Pydantic directly and targets Python 3.12, consistent with the server. It receives already-prepared immutable input and an explicitly injected model client/configuration. The backend retains authorized immutable context preparation, active prompt/reference/LoRA selection, transport and residency/security controls, durable admission, CAS claims, heartbeat/recovery, Layer 3 dispatch/concurrency and full/partial policy, persistence, and deterministic terminal Layer 4 matrix synthesis. No concurrency supervisor or heartbeat moves into the package.

Keep HTTP transport, bounded retries, provider gate, and security in `core.llm`. Define or reuse neutral model request/completion value contracts without duplicating retry budgets. Preserve existing exception names and failure semantics and JSON fields. Remove specialist defaults such as implicit `get_settings`, `get_llm_client`, and `get_llm_model_name` through explicit injection. Deadlines, execution limits, and current repair rules remain unchanged; do not advertise new cancellation behavior.

First extraction excludes standalone `syllabus_alignment` and `curriculum_alignment` evaluators, offline training, CLI/service endpoints, and new queues. They remain server-owned. Change their imports only if a necessary shared contract moves; do not redesign their behavior.

## Invariants and compatibility gates

Treat current executable behavior, tests, schemas, migrations and product constraints as authoritative. Preserve canonical snapshot JSON serialization, schema/default/enum values, ordering and SHA256 verification exactly. `snapshot_contracts.py` is currently pure DTO/ordering/serialization/hash logic; establish one implementation owner in the harness by moving unchanged definitions and serializer/hash. The server keeps snapshot lifecycle, ORM creation/loading, and adapter activation/job-binding/persistence guards. Pure adapter/version validation belongs with harness manifests. Rubric runtime, repository, revisions and snapshots DB responsibilities stay server-side.

Retain default Coordinator adapter 2 and adapter 3 v5 plus all historically supported evaluator versions. Do not activate rubrics or publish models. Preserve Coordinator’s official ten criteria, A-05 `objective_gauging`, and C-01 advisory exclusion from official totals/PDF; retain strict inventory and curriculum requirement. Characterize the known SME synthetic fallback and GAD ungrounded-score behavior without endorsing or silently correcting them. C-01 DPO projector remains deferred and unsupported export behavior is unchanged. Existing PRODUCT.md’s Coordinator-as-curriculum-alignment summary conflicts with PRD restoration wording; flag for reconciliation, do not alter meanings or assert live activation was checked.

Move pure `itso/precheck.py` logic and evidence value contracts where appropriate, but leave retrieval and evidence assembly in server. `supervision/context.py` imports prompt service, document models/paths/ingestion and embeddings: it stays server-side. `supervision/supervisor.py` has ORM chunks/DB; `dispatch.py` owns settings/client and heartbeat/failure isolation: retain orchestration, feeding prepared typed inputs to the harness. For `synthesis/result_integrity.py`, reuse pure semantic validation through public harness contracts/scoring utilities while backend retains binding and storage guards. Do not duplicate ratio-band formulas. Split pure packing in `agents/envelope_map.py` from `load_verified_agent_snapshot` DB access.

Inventory and migrate consumers of rubric/scoring/provenance contracts, including synthesis results, feedback items, DPO projectors/exporter and relevant scripts (`seed_synthetic_dpo_pairs.py`, `run_itso_benchmark.py`, `seed_rubrics.py`). Use only explicit public harness APIs; eliminate private pipeline imports. The PEP 562 agents facade and its public API tests are finite transition aids: remove them after callers migrate, not as permanent aliases. Preserve public single-specialist behavior and Admin all/intentional no-curriculum/historical job behavior. A colleague owns model-validation workflow changes: obtain explicit owner approval/checkpoint before the first affected consumer/import change, including any earlier migration step; do not alter the workflow. If approval is missing, pause at the last runnable boundary rather than preserve permanent aliases or change the owned workflow. Adapter 3 compatibility is a gate to verify, not a pre-existing claim.

## Ordered migration

### 1. Baseline and contract inventory

Before edits, identify existing narrow tests and fixtures for rubric contracts/snapshots, each specialist, synthesis, result integrity, feedback, model validation, DPO exports, and scripts. Record representative input/output fixtures and the current supported evaluator versions. Capture deterministic outcomes: prompts, scores/order, evidence/advisories, failures and provenance; isolate elapsed-time and transport counters where inherently variable. Record current public imports and all callers. Confirm no schema change is required. **Gate:** baseline checks pass or existing failures are recorded for owner disposition; no live DB or service access.

### 2. Package skeleton and pure contracts

Create the package metadata/source tree and public API; extract pure rubric contracts, manifests, calculators and the unchanged snapshot contract/serialization/hash implementation. Move corresponding pure tests with logic. Keep ORM lifecycle in server and adapt it to the single implementation. Add import-boundary checks including dynamic imports and a clean-environment package test with no backend installed. **Gate:** golden snapshot bytes/order/hash and historical manifests unchanged; harness tests run without server, database or retrieval dependencies.

### 3. Explicit model boundary

Introduce typed request/completion inputs and inject client/config from backend adapters. Keep core transport, retries and provider/security controls in place. Preserve error mapping and bounded repair. Add deterministic fake-client tests for request/prompt equivalence and failure behavior. **Gate:** no harness environment/default-model lookup or network stack; no second retry budget.

### 4. Extract specialists one at a time

Move SME, Coordinator, GAD, then ITSO in individually reviewable increments: exercise shared scoring/envelope consumers first, then the policy-retrieval seam. In each increment, migrate that specialist's actual consumers/imports alongside it, and remove the old implementation only afterward; do not leave callers broken for Step 5 or maintain dual pipelines. Move pure ITSO precheck and needed pure evidence values; retain evidence retrieval/context assembly in server. Retain specialist-specific domain structure. **Gate per specialist:** golden behavior comparisons pass, including failure and provenance behavior, existing limits/repair and relevant historical evaluator variants.

### 5. Remaining crosscutting consumer closure

Migrate any remaining synthesis result integrity/results, feedback, envelope mapping, DPO projectors/exporter and scripts to the explicit public API. Split DB loading from pure mapping. Retain backend persistence, ownership/binding guards and terminal Layer 4 matrix. Model-validation owner approval must precede the first affected consumer/import change, including in earlier steps; if missing, pause at the last runnable boundary without permanent aliases or changes to the owned workflow. Remove private pipeline imports and the finite PEP 562 facade/tests when no callers remain. **Gate:** Admin all and intentional partial semantics, historical jobs, single-specialist behavior, failure isolation, session/thread isolation, result tamper checks and output shapes are verified; owner checkpoint is recorded.

### 6. Packaging, CI and documentation

Use the existing server uv project with a declared relative local library dependency/source; there is no root uv workspace. The pnpm workspace’s JS `libs/*` inclusion does not create a Python workspace. Avoid toolchain overhaul, dummy `package.json`, and lock changes until execution. Inspect Docker build context, ignore rules, compose mounts, CI and scripts. Update Docker dependency-copy/install order to make the library available before local dependency resolution in both dev and production builds. Verify frozen install/wheel or equivalent clean packaging smoke with `PYTHONPATH` unable to mask packaging errors. Update architecture and scoped agent guidance plus relevant root docs during execution, clearly documenting then-current state rather than prematurely claiming extraction complete. **Gate:** clean image/package build and CI installation agree with local package boundaries.

### 7. Integration and rollout decision

Run targeted harness tests and affected backend tests throughout; reserve the broad regression suite for the completed cross-cutting integration. Backend checks include queue ownership/recovery, thread session isolation, full/partial outcomes, persistence, result tampering and PDF. Reconcile product wording conflict as a separate explicit documentation decision. No DB schema migration is expected; if extraction unexpectedly requires schema or score API changes, STOP and revise the plan. Do not reset databases, rewrite hashes, automatically activate models, or deploy without approval. For approved deployment only, quiesce the drainer and restore the prior artifact on rollback; communicate exact approval and recovery steps. Real-model, deployed-Docker, Postgres and browser readiness are separate optional gates, not claims supported by deterministic tests.

## Completion evidence

Completion requires independently runnable, reviewable increments; staging or commits require explicit user approval; pure package tests in a clean environment; import-boundary enforcement; exact contract/snapshot fixtures; deterministic specialist and consumer equivalence; historical-version coverage; model-validation owner approval; packaging/CI evidence; and targeted backend regression evidence. Record deferred issues and any intentionally variable comparisons. This handoff is not authorization to perform runtime changes or deployment, and currently does not claim any implementation or tests have begun.
