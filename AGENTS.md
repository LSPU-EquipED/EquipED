## Authority And Scope

- Root instructions apply repo-wide; scoped `AGENTS.md` files (in `apps/server/`, `apps/faculty/`, `apps/admin/`, `docs/`) add domain-specific enforcement without weakening root rules.
- Executable behavior is authoritative through current code, API and schema contracts, migrations, and tests.
- `PRODUCT.md` and `PRD.md` govern product intent, roles, scope, and constraints; `ARCHITECTURE.md` governs system structure, and `DESIGN.md` governs design-system and UX direction.
- OpenSpec material is historical reference only. It is not an implementation contract, required workflow, or source of current authority.
- Conflicts between code, tests, migrations, and product documentation must be surfaced and reconciled explicitly, never chosen silently.

## Product Invariants

- EquipED evaluates LSPU SCC SLMs against institutional reference documents and rubrics.
- Human review is authoritative; generated evaluations and recommendations are advisory only.
- Data privacy, local data residency, and strict ownership scoping are core invariants. External data sharing is prohibited unless explicitly configured.
- SLMs are direct evaluation input and are never embedded into vector storage.
- Partial completion is permitted only for explicit intentional partial workflows, such as acknowledged no-curriculum intent; unhandled failures in full or partial evaluations remain failed.

## Stable Architecture

- Backend is a single-process FastAPI modular monolith; `apps/server/core/` is infrastructure-only and contains no business logic.
- Frontend comprises two feature-driven React applications: `apps/faculty` and `apps/admin`, built on shared libraries under `libs/*` (`@equiped/types`, `@equiped/api-client`, `@equiped/ui`, `@equiped/auth`). Features within each app remain self-contained with no cross-feature imports.
- In-process durable evaluation admission and recovery: Layer 3 specialist agent outputs are persisted to the database, followed by deterministic Layer 4 synthesis producing the terminal monitoring matrix. No further automated layers run.
- Module and feature boundaries are strictly scoped.
- No external message queues (e.g. Celery/Redis) or distributed execution systems may be introduced without explicit user approval and corresponding updates to authoritative code, tests, and product documentation.

## Working Rules

- Read relevant code, tests, schemas, migrations, `PRODUCT.md`, `PRD.md`, `ARCHITECTURE.md`, and `DESIGN.md` before implementation.
- Keep tests and product documentation aligned with material behavior or architecture changes.
- Prefer minimal diffs, execute narrow verification checks, and call out material assumptions explicitly.

