## Scope

- Rules in this file apply under `docs/` and inherit repo-wide authority, OpenSpec workflow, and product invariants from root `AGENTS.md`.
- Documentation in `docs/` provides supporting product and architecture reference material, not implementation contracts.

## Documentation Guardrails

- Avoid duplicating module inventories, route listings, runtime tables, or low-level implementation mechanisms in docs.
- Clearly distinguish between settled architecture, active changes, open/deferred proposals, and historical records.
- Explicitly distinguish intentional partial evaluation success from unhandled runtime failures.
- Never use documentation edits to silently change system architecture, authentication boundaries, privacy/residency commitments, or human authority principles.

## Validation And Quality

- Cross-check documentation against canonical specs (`openspec/specs/`) and current codebase reality.
- Verify internal links, file paths, and referenced spec anchors.
- If conflicts arise between documentation, specs, and code, report them separately for explicit reconciliation rather than silently modifying docs to mask inconsistencies.
