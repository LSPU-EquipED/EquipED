## Scope

- This directory is only responsible for backend architecture and backend implementation under `server/`.
- Preserve the FastAPI modular monolith shape defined in `docs/TDD.md`.

## Backend Guardrails

- `core/` is infrastructure-only. No business logic belongs there.
- Each module owns its own router, service logic, models, schemas, and module-local exceptions.
- Modules should communicate through explicit service interfaces or shared contracts, not by reaching into another module's internals.
- Keep the planned module split intact: `documents`, `embeddings`, `evaluations`, `agents`, `synthesis`, `feedback`, `admin`.
- Preserve the evaluation lifecycle exactly: `SUBMITTED -> PREPROCESSING -> EMBEDDING -> EVALUATING -> SYNTHESIZING -> COMPLETED|FAILED`.
- Phase 1 remains sequential and uses FastAPI `BackgroundTasks`; do not prematurely introduce Celery, Redis, or parallel agent execution.

## Current Reality

- Files in this directory are currently placeholders only.
- Do not imply that DB wiring, FastAPI app wiring, Alembic config, models, or runtime services are already implemented if they are not.

## Before Making Backend Changes

- Read `../docs/TDD.md` first.
- Prefer `../docs/TDD.md` over `../docs/PRD.md` for backend structure details.
- Keep compliance constraints in mind: human review is authoritative and document data handling must remain conservative.
