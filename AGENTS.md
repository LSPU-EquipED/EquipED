## Authority And Scope

- Root instructions apply repo-wide; scoped `AGENTS.md` files (in `server/`, `client/`, `docs/`) add domain-specific enforcement without weakening root rules.
- `openspec/specs/` is the canonical source for implementation contracts and accepted product behavior.
- `docs/PRD.md` provides supporting scope, roles, and constraints; it does not override canonical specifications.
- Conflicts between code, specs, and documentation must be surfaced and reconciled explicitly, never chosen silently.

## OpenSpec Workflow

- Active material changes are tracked under `openspec/changes/<change>/`.
- `openspec/changes/archive/` contains historical evidence only; archived deltas are never current authority and cannot be reapplied without a new change proposal.
- Preserve newer canonical wording when reconciling specifications against changes.
- Keep proposal, design, tasks, implementation, and canonical specs aligned throughout the change lifecycle.

## Product Invariants

- EquipED evaluates LSPU SCC SLMs against institutional reference documents and rubrics.
- Human review is authoritative; generated evaluations and recommendations are advisory only.
- Data privacy, local data residency, and strict ownership scoping are core invariants. External data sharing is prohibited unless explicitly configured.
- SLMs are direct evaluation input and are never embedded into vector storage.
- Partial completion is permitted only for explicit intentional partial workflows, such as acknowledged no-curriculum intent; unhandled failures in full or partial evaluations remain failed.

## Stable Architecture

- Backend is a single-process FastAPI modular monolith; `server/core/` is infrastructure-only and contains no business logic.
- Frontend is a feature-driven React application; `client/src/features/*` remain self-contained with no cross-feature imports, and `client/src/shared/` is restricted to proven multi-feature utilities.
- In-process durable evaluation admission and recovery: Layer 3 specialist agent outputs are persisted to the database, followed by deterministic Layer 4 synthesis producing the terminal monitoring matrix. No further automated layers run.
- Module and feature boundaries are strictly scoped.
- No external message queues (e.g. Celery/Redis) or distributed execution systems may be introduced without an accepted spec contract.

## Working Rules

- Read relevant canonical specs in `openspec/specs/` first before implementation; consult `docs/PRD.md` for supporting context.
- Refer to `PRODUCT.md` and `DESIGN.md` for product personality, design tokens, and UI component standards.
- Prefer minimal diffs, execute narrow verification checks, and call out material assumptions explicitly.

