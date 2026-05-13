## Scope

- This directory covers backend implementation under `server/`.
- Preserve the FastAPI modular monolith shape defined in `openspec/specs/` and supported by `docs/TDD.md`.

## Backend Guardrails

- `core/` is infrastructure-only. No business logic belongs there.
- Each module owns its own router, service logic, models, schemas, and module-local exceptions.
- Modules should communicate through explicit service interfaces or shared contracts, not by reaching into another module's internals.
- Keep the module split intact: `documents`, `embeddings`, `evaluations`, `agents`, `synthesis`, `feedback`, `admin`.
- Preserve the evaluation contract boundary: safe pre-agent lifecycle only, with Layer 3 failure handled honestly per `openspec/specs/evaluations/spec.md`.
- Phase 1 remains sequential and uses FastAPI `BackgroundTasks`; do not prematurely introduce Celery, Redis, or parallel agent execution.
- Document ownership is per-user for all roles.
- Human roles are `admin` and `faculty`; evaluator domains/agents are `sme`, `coordinator`, `gad`, and `itso`.

## Before Making Backend Changes

- Read `../openspec/specs/` first, then `../docs/TDD.md` and `../docs/PRD.md` as support.
- Prefer `../openspec/specs/` over `../docs/TDD.md` and `../docs/PRD.md` when they differ.
- Keep compliance constraints in mind: human review is authoritative and document data handling must remain conservative.
