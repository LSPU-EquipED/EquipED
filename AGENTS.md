## Architectural Scope

- `openspec/specs/` is the canonical implementation contract source.
- Use `docs/TDD.md` and `docs/PRD.md` as supporting reference docs; do not let them override `openspec/specs/`.
- Keep the repo aligned with current implemented behavior and current spec state; do not reintroduce stale scaffold-only assumptions.

## Highest-Value Files

- `openspec/specs/` — implementation contracts and accepted product behavior.
- `docs/TDD.md` — supporting technical blueprint and architecture notes.
- `docs/PRD.md` — supporting scope, roles, deliverables, and constraints.
- `server/AGENTS.md` — backend guardrails for the modular monolith.
- `client/AGENTS.md` — frontend guardrails for the feature-driven client.
- `docs/AGENTS.md` — documentation guardrails for spec edits.

## Architecture To Preserve

- Backend remains a single-process FastAPI modular monolith. Each module owns its own router, service layer, models, schemas, and exceptions.
- `server/core/` is infrastructure-only. Do not move business rules or orchestration logic into `core/`.
- Frontend remains feature-driven. `client/src/features/*` must stay self-contained and must not import from one another.
- `client/src/shared/` is strictly for code proven to be reused by at least two features.
- Evaluation jobs follow the contract in `openspec/specs/evaluations/spec.md`: Layer 3 multi-agent evaluation runs via FastAPI BackgroundTasks with supervisor-managed ThreadPoolExecutor for parallel agent execution. Layer 4 synthesis produces the monitoring matrix as the terminal output; no further automated layers run. Celery/Redis remain deferred.

## Product And Compliance Constraints

- Scope is limited to SLM evaluation for LSPU SCC using institutional rubrics and reference documents.
- Human review is authoritative; generated evaluations are advisory only.
- Data privacy and local data residency are core constraints. Do not expand external data sharing beyond what the docs allow.
- Open decisions stay in the supporting docs unless promoted through `openspec/specs/`.

## Repo Map

- This repository supports EquipED, a multi-agent SLM evaluation system for LSPU SCC.
- `README.md` — active setup/runtime guidance.
- `openspec/specs/` — implementation contracts.
- `docs/PRD.md` — supporting product scope and constraints.
- `docs/TDD.md` — supporting technical blueprint.
- `server/` — backend implementation and module boundaries.
- `client/` — frontend implementation and feature boundaries.
- `uploads/`, `chroma_data/`, and `equiped_dev.db` — local runtime data at the repository root.

### Key Entry Points

- `server/main.py` — FastAPI app entry.
- `client/src/main.tsx` — frontend bootstrap.
- `client/src/app/router.tsx` — router.
- `client/src/app/providers.tsx` — provider composition.

### Directory Responsibilities

- `server/core/` — shared infrastructure only.
- `server/modules/documents/` — PDF upload and ingestion.
- `server/modules/embeddings/` — reference/rubric vectorization and retrieval only.
- `server/modules/evaluations/` — evaluation job lifecycle.
- `server/modules/agents/` — supervisor plus SME/coordinator/GAD/ITSO evaluators.
- `server/modules/synthesis/` — scoring, flags, reports, and monitoring matrix.
- `server/modules/feedback/` — preference logging.
- `server/modules/admin/` — prompt management and preference review.
- `server/db/` — migration/config scaffold only.
- `server/tests/` — integration and unit tests matching the module structure.
- `client/src/app/` — routing tree, global providers, and layout shell.
- `client/src/features/` — feature-owned components, hooks, API files, and types.
- `client/src/shared/` — intentionally sparse shared layer for code reused by 2+ features.
- `docs/` — PRD/TDD documentation only.

### Execution Flow Constraints

- Authenticated document workflows must remain ownership-scoped.
- Evaluation must execute Layer 3 multi-agent evaluation and stop honestly at the Layer 4 boundary defined in `openspec/specs/evaluations/spec.md`.
- Later-phase multi-agent behavior must follow the spec contract rather than implied implementation details.
- SLMs are direct evaluation input; do not embed them into ChromaDB.
- Only reference documents (syllabus, curriculum), rubrics, and policy documents (admin-only Chroma collection) belong in the vector store. SLMs are never embedded.
- The EMBEDDING lifecycle status has been removed; do not reintroduce it.
- chroma_data, uploads directories, and equiped_dev.db are anchored to the repository root.
- Local OCR must fail closed on errors; ingestion does not proceed with partial or degraded OCR output.
- Partial evaluations (curriculum missing, Coordinator skipped) produce job status COMPLETED and matrix status COMPLETED_PARTIAL — evaluation completes honestly with gaps flagged.
- ITSO policy evidence delivery defaults to disabled; when enabled it is local/residency-gated — no external policy data egress.
- Per-agent model routing and fallback must preserve attribution; each evaluation trace records which model generated each agent output.
- Admin-only Model Validation surface; optional toxicity check runs local-only.

## Working Rules

- Read `openspec/specs/` first for implementation behavior.
- Use `docs/TDD.md` and `docs/PRD.md` only to resolve supporting context.
- Call out assumptions explicitly in commits and PRs.

## Design And Branding

- Read [PRODUCT.md](PRODUCT.md) to understand target users, strategic product purpose, brand personality, and anti-references.
- Read [DESIGN.md](DESIGN.md) for custom theme tokens (LSPU SCC colors), typography rules, flat elevation principles, and component standards.

