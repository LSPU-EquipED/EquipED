## Why

The Admin feature currently concentrates multiple independent capabilities in
large page files: Model Validation is 1,600+ lines and Reference Library is
800+ lines. Queries, mutations, input state, dialogs, helpers, and substantial
UI sections coexist in those pages, making behavior difficult to review and
future work risky.

## What Changes

- Reorganize Model Validation as a self-contained `features/admin/model-validation/`
  subfeature with page, component, hook, API, type, and utility ownership.
- Reorganize Reference Library as a self-contained
  `features/admin/reference-library/` subfeature with the same boundaries.
- Reduce each route page to feature orchestration; extract cohesive sections,
  feature-private state/query hooks, and feature-private helpers.
- Move Model Validation’s existing confusion-matrix utility tests alongside the
  subfeature utilities.
- Add a narrow `features/admin/index.ts` route-facing export surface while
  preserving all current routes, backend contracts, user flows, and visual
  behavior.
- Keep smaller Admin capabilities in their current locations for now; do not
  create generic cross-feature tables, dialogs, or shared abstractions.

## Capabilities

### New Capabilities

- `admin-subfeature-organization`: Defines feature-local ownership and route
  boundaries for Admin subfeatures without changing user-facing behavior.

### Modified Capabilities

None.

## Impact

- Affected client area: `client/src/features/admin/`, including router imports
  and existing Model Validation utility tests.
- API endpoints, runtime request/response shapes, database models, routes,
  interaction behavior, styling, dependencies, and backend code remain
  unchanged. Feature-private TypeScript declarations and import paths relocate
  to their owning subfeature.
- The refactor creates no cross-feature imports between Model Validation and
  Reference Library.
