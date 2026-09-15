## Scope

- Rules in this file apply under `docs/` and inherit repo-wide authority and product invariants from root `AGENTS.md`.
- Root `PRODUCT.md` and `PRD.md` govern product intent, roles, scope, and constraints; root `ARCHITECTURE.md` governs system structure, and root `DESIGN.md` governs design-system and UX direction.

## Documentation Guardrails

- Avoid duplicating module inventories, route listings, runtime tables, or low-level implementation mechanisms in docs.
- Clearly distinguish between settled architecture, active changes, open/deferred proposals, and historical records.
- Explicitly distinguish intentional partial evaluation success from unhandled runtime failures.
- Never use documentation edits to silently change system architecture, authentication boundaries, privacy/residency commitments, or human authority principles.

## Validation And Quality

- Cross-check documentation against current code, tests, schemas, migrations, and product documentation.
- Verify internal links and file paths.
- If conflicts arise between documentation and executable behavior, report them separately for explicit reconciliation rather than silently masking inconsistencies.
