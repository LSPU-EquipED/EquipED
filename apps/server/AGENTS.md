## Scope

- Applies to all backend code under `apps/server/` and inherits root `AGENTS.md`.

## Backend Boundaries

- Single-process FastAPI modular monolith.
- `apps/server/core/` is infrastructure-only; business rules and orchestration logic never belong in `core/`.
- Domain modules own their own routing, service layer, models, schemas, and module-local exceptions.
- `modules/alignment/` is an organizational namespace for independent curriculum and syllabus checks. Each child owns its application workflow, evaluator and persistence; these standalone checks remain in the server and separate from the four specialist agent harnesses.
- Modules communicate exclusively through public service interfaces or shared contracts, never reaching into internal module implementations.
- `apps/server/main.py` composes app infrastructure, lifecycle hooks, middleware, and module routers; domain behavior remains in domain modules.

## Evaluation Enforcement

- Evaluation execution is backed by durable DB-backed FIFO admission with ownership-safe compare-and-swap (CAS) claim tokens, heartbeat tracking, startup recovery, and a single worker/drainer.
- The HTTP request trigger initiates admission but is not the execution contract.
- Specialist pipelines, prompts, scoring, evidence interpretation, public-reference tools, semantic rubric contracts and snapshot hashing live in `libs/evaluation-harness`; never duplicate them in backend consumers. Production dispatch calls the public harness API with an immutable `EvaluationRequest`, explicit execution/tool configuration and a model-client adapter wrapping core transport. Backend retains authorized local storage/retrieval, model resolution, snapshot/storage identity checks and persistence.
- Evaluation integration supplies authorized inputs and runs specialist tasks while the owning thread maintains durable claims and heartbeats. No specialist harness implementation belongs under server modules. The evaluation orchestrator persists Layer 3 outputs and runs deterministic Layer 4 synthesis terminally. Saved-assessment database readers remain backend-owned; preserve existing result endpoints and integrity guards when relocating them.
- Historical evidence-only ITSO assessment models and read services belong to `modules/itso_assessments/`; current ITSO execution belongs to the harness library. Preserve retained historical records, frozen evidence and unavailable scores without restoring retired approval or write workflows.
- Preserve explicit full/partial completion truth: full evaluations never downgrade silently; partial evaluation succeeds only when all non-skipped required agents succeed.
- Never share SQLAlchemy sessions or ORM-attached state across worker threads; pass immutable precomputed context into worker threads.

## Data And Security

- Enforce authentication and strict ownership verification across service boundaries; availability of shared institutional references never weakens SLM or evaluation job ownership isolation.
- SLMs are direct evaluation inputs and are never embedded into vector storage; only spec-authorized reference, rubric, and policy documents are stored in Chroma collections. Explicitly configured Chroma Cloud is an authorized storage option; preserve document scoping and the private-model gate for policy delivery.
- OCR and document ingestion must fail closed on errors without persisting partial or degraded ingestion state.
- Keep policy evidence and validation residency-gated and strictly local; report bounded, non-sensitive failure errors.

## Verification

- Run commands from repository root via package scripts or `apps/`:
- Linting check: `pnpm server:lint` or `cd apps && uv run --project server ruff check server ../libs/evaluation-harness`
- Formatting check: `pnpm server:format` or `cd apps && uv run --project server ruff format --check server ../libs/evaluation-harness`
- Targeted tests: run narrow test suites matching modified areas (e.g., `cd apps && uv run --project server pytest server/tests/<area>`).
- Broader suite: run `pnpm server:test` (or `cd apps && uv run --project server pytest`) only for cross-module or integration changes.
