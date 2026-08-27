## Scope

- Applies to all backend code under `server/` and inherits root `AGENTS.md`.

## Backend Boundaries

- Single-process FastAPI modular monolith.
- `server/core/` is infrastructure-only; business rules and orchestration logic never belong in `core/`.
- Domain modules own their own routing, service layer, models, schemas, and module-local exceptions.
- Modules communicate exclusively through public service interfaces or shared contracts, never reaching into internal module implementations.
- `server/main.py` composes app infrastructure, lifecycle hooks, middleware, and module routers; domain behavior remains in domain modules.

## Evaluation Enforcement

- Evaluation execution is backed by durable DB-backed FIFO admission with ownership-safe compare-and-swap (CAS) claim tokens, heartbeat tracking, startup recovery, and a single worker/drainer.
- The HTTP request trigger initiates admission but is not the execution contract.
- The supervisor owns Layer 3 parallel specialist execution; evaluation orchestrator persists agent outputs and runs deterministic Layer 4 synthesis terminally.
- Preserve explicit full/partial completion truth: full evaluations never downgrade silently; partial evaluation succeeds only when all non-skipped required agents succeed.
- Never share SQLAlchemy sessions or ORM-attached state across worker threads; pass immutable precomputed context into worker threads.

## Data And Security

- Enforce authentication and strict ownership verification across service boundaries; availability of shared institutional references never weakens SLM or evaluation job ownership isolation.
- SLMs are direct evaluation inputs and are never embedded into vector storage; only spec-authorized reference, rubric, and policy documents are stored in local Chroma collections.
- OCR and document ingestion must fail closed on errors without persisting partial or degraded ingestion state.
- Keep policy evidence and validation residency-gated and strictly local; report bounded, non-sensitive failure errors.

## Verification

- Run commands from the repository root.
- Linting check: `uv run --project server ruff check server`
- Formatting check: `uv run --project server ruff format --check server`
- Targeted tests: run narrow test suites matching modified areas (e.g., `uv run --project server pytest server/tests/<area>`).
- Broader suite: run `uv run --project server pytest server/tests` only for cross-module or integration changes.
