## Architectural Scope

- This repository is still architecture-first. The checked-in `server/` and `client/` trees are scaffolds, not working application code.
- Treat `docs/TDD.md` as the primary implementation blueprint and `docs/PRD.md` as the product and constraint document.
- `docs/TDD.md` and `docs/PRD.md` are draft documents. Do not convert TBD items into implied final architecture.

## Highest-Value Files

- `docs/TDD.md` — source of truth for planned module boundaries, route map, API shape, schemas, and deferred work.
- `docs/PRD.md` — scope, roles, deliverables, and non-functional constraints.
- `server/AGENTS.md` — backend guardrails for the modular monolith scaffold.
- `client/AGENTS.md` — frontend guardrails for the feature-driven scaffold.
- `docs/AGENTS.md` — documentation-only guardrails for spec edits.

## Current Repo Reality

- `server/` exists as placeholder scaffolding for a FastAPI modular monolith: `core/`, `modules/`, `db/`, and `tests/` are present, but runtime wiring and business logic are not.
- `client/` exists as placeholder scaffolding for a React + Vite + TanStack frontend: `src/app/`, `src/features/`, and `src/shared/` are present, but routing, providers, API clients, and UI logic are not.
- `uploads/` and `chroma_data/` are local artifact directories and should remain local-only.
- There are still no runnable manifests, lockfiles, CI workflows, or verified tool configs. Do not invent commands like `npm test`, `pnpm dev`, `pytest`, or migration commands unless those files are later added.

## Planned Architecture To Preserve

- Backend remains a single-process FastAPI modular monolith. Each module owns its own router, service layer, models, schemas, and exceptions.
- `server/core/` is infrastructure-only. Do not move business rules or orchestration logic into `core/`.
- Frontend remains feature-driven. `client/src/features/*` must stay self-contained and must not import from one another.
- `client/src/shared/` is strictly for code proven to be reused by at least two features.
- Evaluation jobs follow `SUBMITTED -> PREPROCESSING -> EMBEDDING -> EVALUATING -> SYNTHESIZING -> COMPLETED|FAILED`.
- Phase 1 execution remains sequential via FastAPI `BackgroundTasks`; parallel execution and Celery/Redis are deferred.

## Product And Compliance Constraints

- Scope is limited to SLM evaluation for LSPU SCC using institutional rubrics and reference documents.
- Human review is authoritative; generated evaluations are advisory only.
- Data privacy and local data residency are core constraints. Do not expand external data sharing beyond what the docs allow.
- Open decisions still exist in `docs/TDD.md` Section 13, including auth strategy, upload limit, Anthropic data-handling confirmation, prompt-update thresholds, chunking tuning, and PDF export library.

## Repo Map

### Current Responsibility

This repository currently holds the planned architecture and scaffold for EquipED, a proposed multi-agent SLM evaluation system for LSPU SCC. It is not yet a runnable application.

### What Exists Now

- `README.md` — empty.
- `docs/PRD.md` — product scope, roles, deliverables, requirements, and constraints.
- `docs/TDD.md` — technical blueprint for the planned system.
- `server/` — backend scaffold only.
- `client/` — frontend scaffold only.
- `uploads/` and `chroma_data/` — local runtime data directories kept in repo only via `.gitkeep`.

### Planned / Scaffolded Entry Points

- `server/main.py` — FastAPI app entry placeholder.
- `client/src/main.tsx` — frontend bootstrap placeholder.
- `client/src/app/router.tsx` — router placeholder.
- `client/src/app/providers.tsx` — provider placeholder.

### Directory Responsibilities

- `server/core/` — shared infrastructure only.
- `server/modules/documents/` — PDF upload and ingestion.
- `server/modules/embeddings/` — vectorization and retrieval.
- `server/modules/evaluations/` — evaluation job lifecycle.
- `server/modules/agents/` — supervisor plus SME/coordinator/GAD/ITSO evaluators.
- `server/modules/synthesis/` — scoring, flags, reports, and monitoring matrix.
- `server/modules/feedback/` — preference logging.
- `server/modules/admin/` — prompt management and preference review.
- `server/db/` — migration/config scaffold only.
- `server/tests/` — test scaffold only.
- `client/src/app/` — routing tree, global providers, and layout shell.
- `client/src/features/` — feature-owned components, hooks, API files, and types.
- `client/src/shared/` — intentionally sparse shared layer for code reused by 2+ features.
- `docs/` — PRD/TDD documentation only.

### Planned Execution Flow

1. User uploads PDFs.
2. Backend preprocesses and OCRs documents.
3. Text is chunked, embedded, and stored in ChromaDB.
4. Supervisor runs four evaluator agents.
5. Results are synthesized into scorecards, flags, reports, and monitoring updates.
6. Evaluator feedback is logged for later prompt tuning.

## Working Rules

- Read `docs/TDD.md` before making structural decisions.
- When PRD and TDD differ, prefer TDD for implementation details and PRD for scope/constraints.
- Call out assumptions explicitly in commits and PRs because many details are still TBD.
