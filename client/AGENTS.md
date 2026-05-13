## Scope

- This directory covers frontend implementation under `client/`.
- Preserve the feature-driven structure defined in `openspec/specs/` and supported by `docs/TDD.md`.

## Frontend Guardrails

- `src/features/*` owns feature-local components, hooks, API files, and types.
- Features must not import from each other directly.
- `src/shared/` is strictly for code proven to be reused by at least two features.
- `src/app/` is for app shell concerns only: routing tree, providers, and layout.
- Do not turn `shared/` into a dumping ground for unfinished or single-feature code.
- Route access must follow the hydrated backend session and role from `admin` or `faculty`.
- Document views and actions must respect per-user ownership.

## Before Making Frontend Changes

- Read `../openspec/specs/` first, then `../docs/TDD.md` for supporting structure notes.
- Prefer promoting code to `shared/` only after real duplication exists.
- Keep role-gated routes, document ownership, and admin/faculty surfaces aligned with the implementation contracts.
