## Scope

- This directory is only responsible for frontend architecture and frontend implementation under `client/`.
- Preserve the feature-driven structure defined in `docs/TDD.md`.

## Frontend Guardrails

- `src/features/*` owns feature-local components, hooks, API files, and types.
- Features must not import from each other directly.
- `src/shared/` is strictly for code proven to be reused by at least two features.
- `src/app/` is for app shell concerns only: routing tree, providers, and layout.
- Do not turn `shared/` into a dumping ground for unfinished or single-feature code.

## Current Reality

- Files in this directory are scaffold placeholders only.
- Router definitions, provider composition, API clients, query logic, and actual UI behavior are still deferred.

## Before Making Frontend Changes

- Read `../docs/TDD.md` first, especially repository structure and route architecture.
- Prefer promoting code to `shared/` only after real duplication exists.
- Keep role-gated routes, monitoring matrix scope, and admin surfaces aligned with the TDD.
