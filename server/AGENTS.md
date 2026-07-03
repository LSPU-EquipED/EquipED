## Scope

- This directory covers backend implementation under `server/`.
- Preserve the FastAPI modular monolith shape defined in `openspec/specs/` and supported by `docs/TDD.md`.

## Backend Guardrails

- `core/` is infrastructure-only. No business logic belongs there.
- Each module owns its own router, service logic, models, schemas, and module-local exceptions.
- Modules should communicate through explicit service interfaces or shared contracts, not by reaching into another module's internals.
- Keep the module split intact: `documents`, `embeddings`, `evaluations`, `agents`, `synthesis`, `feedback`, `admin`.
- Preserve the evaluation contract boundary: Layer 3 multi-agent evaluation runs, Layer 4 is the honest stop per `openspec/specs/evaluations/spec.md`.
- Phase 1 uses FastAPI `BackgroundTasks` with parallel agent execution via `ThreadPoolExecutor` for I/O-bound LLM calls. Each agent uses a distinct model to avoid rate-limit contention. Celery/Redis remain deferred.
- Document ownership is per-user for all roles.
- The embeddings module handles reference and rubric vectorization only; SLMs skip embedding entirely.
- Human roles are `admin` and `faculty`; evaluator domains/agents are `sme`, `coordinator`, `gad`, and `itso`.
- SLMs are direct evaluation input and are NOT embedded into ChromaDB.
- Only reference documents (syllabus, curriculum) and rubrics are embedded into the vector store.
- The evaluation lifecycle is: SUBMITTED → PREPROCESSING → EVALUATING → SYNTHESIZING → COMPLETED. There is no EMBEDDING status.
- The chroma_stored validation gate only applies to embedding-required documents (reference/rubric), not SLMs.
- chroma_data, uploads directories, and equiped_dev.db are anchored to the repository root via Path(__file__) resolution.

## Before Making Backend Changes

- Read `../openspec/specs/` first, then `../docs/TDD.md` and `../docs/PRD.md` as support.
- Prefer `../openspec/specs/` over `../docs/TDD.md` and `../docs/PRD.md` when they differ.
- Keep compliance constraints in mind: human review is authoritative and document data handling must remain conservative.
