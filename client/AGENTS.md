## Scope

- This directory covers frontend implementation under `client/`.
- Preserve the feature-driven structure defined in `openspec/specs/` and supported by `docs/TDD.md`.

## Frontend Guardrails

- `src/features/*` owns feature-local components, hooks, API files, types, and utils (under `features/<feature>/utils`).
- Integration and component tests live under `components/__tests__/`; utility tests under `utils/**/__tests__/`.
- Features must not import from each other directly.
- `src/shared/` is strictly for code proven to be reused by at least two features.
- `src/app/` is for app shell concerns only: routing tree, providers, and layout.
- Do not turn `shared/` into a dumping ground for unfinished or single-feature code.
- Route access must follow the hydrated backend session and role from `admin` or `faculty`.
- Document views and actions must respect per-user ownership.
- Faculty upload SLMs only (direct evaluation input). Admin manages reference documents, curricula, rubrics, and policy documents.
- Curriculum confirmation and explicit partial-decision UX must be presented to the user before evaluation starts.
- Evaluation status rendering must truthfully reflect terminal (COMPLETED), partial (COMPLETED_PARTIAL), and failed (FAILED) states.
- Admin-only surfaces: Policy Library (upload/view policy documents) and Model Validation (local-only toxicity check, model configuration).
- Client-side PDF export must preserve result truthfulness and must not expose raw chunk IDs.

## Before Making Frontend Changes

- Read `../openspec/specs/` first, then `../docs/TDD.md` for supporting structure notes.
- Prefer promoting code to `shared/` only after real duplication exists.
- Keep role-gated routes, document ownership, and admin/faculty surfaces aligned with the implementation contracts.
